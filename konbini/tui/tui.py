import curses
import json
import subprocess
import os
from datetime import datetime
from time import sleep

def curses_init(fg, bg):
    rows, cols = os.popen('stty size', 'r').read().split()
    screen = curses.initscr()
    curses.noecho()
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, fg, bg)
    curses.init_pair(2, bg, fg)
    screen.keypad(1)
    screen.nodelay(1)
    screen.idlok(0)
    screen.idcok(0)
    screen.bkgd(curses.color_pair(1))
    return screen, int(rows), int(cols)


def check_term_size(menu):
    if (menu.rows//2 - menu.largest_list//2 - 4) < 0 or (menu.cols - 24) < 0:
        menu.screen.erase()
        curses.endwin()
        print("Error: Terminal is too small.")
        exit(1)


def tui_loop(rc_path):
    ch = None
    menu = Menu(rc_path)
    check_term_size(menu)
    menu.draw_statics()
    menu.draw_datetime()
    menu.draw_all_pads()
    menu.draw_active()
    while(ch != ord('q')):
        ch = menu.screen.getch()
        if ch == ord('\t'):
            menu.draw_active(highlight=False)
            menu.active = (menu.active + 1) % len(menu.pads)
            menu.draw_active()
        if ch == curses.KEY_DOWN:
            menu.pads[menu.active].selection = ((menu.pads[menu.active].selection + 1)
                                                % len(menu.pads[menu.active].item_list))
            menu.draw_active()
        if ch == curses.KEY_UP and menu.pads[menu.active].selection == 0:
            menu.pads[menu.active].selection = len(
                menu.pads[menu.active].item_list)
            menu.draw_active()
        if ch == curses.KEY_UP and menu.pads[menu.active].selection != 0:
            menu.pads[menu.active].selection = (
                menu.pads[menu.active].selection - 1)
            menu.draw_active()
        if ch == 10:
            menu.pads[menu.active].spawn()
            menu.draw_active()
        if ch == ord('s'):
            # curses.echo()
            menu.search_pad.enter_search()
            curses.noecho()
        sleep(0.01)
        menu.draw_datetime()
        if curses.is_term_resized(menu.rows, menu.cols):
            menu.screen.erase()
            menu.get_dimensions()
            check_term_size(menu)
            menu.draw_statics()
            menu.draw_datetime()
            menu.search_pad.set_dimensions(menu.rows//2 - menu.largest_list//2 - 2,
                                           menu.cols//5,
                                           3*menu.cols//5)
            menu.draw_all_pads()
            menu.draw_active()
    menu.screen.erase()
    curses.endwin()
    exit()


class SearchPad():

    def __init__(self, ypos, x_left, n_cols, cmd, search_engine, color_pair,
                 reverse=True):
        self.ypos = ypos
        self.x_left = x_left
        self.n_cols = n_cols
        self.pad = curses.newwin(1, self.n_cols, self.ypos, self.x_left)
        self.cmd = cmd
        self.search_engine = search_engine
        self.color_pair = color_pair
        self.pad.bkgd(self.color_pair)

    def set_dimensions(self, ypos, x_left, cols):
        self.ypos = ypos
        self.x_left = x_left
        self.n_cols = cols
        self.pad = curses.newwin(1, self.n_cols, self.ypos, self.x_left)
        self.pad.bkgd(self.color_pair)

    def draw_pad(self, search_term=None):
        self.pad.erase()
        if search_term and len(search_term + "_") < (self.n_cols - 9):
            self.pad.addstr(0, 0, " Search: " + str(search_term) + "_")
        if search_term and len(search_term + "_") >= (self.n_cols - 9):
            shift = len(search_term + "_") - (self.n_cols - 10)
            self.pad.addstr(0, 0, " Search: " + str(search_term[shift:]) + "_")
        else:
            self.pad.addstr(0, 0, " Search: ")
        self.pad.refresh()

    def enter_search(self):
        search_string = ""
        sch = None
        while(sch != 10):
            sch = self.pad.getch()
            if sch == 10:
                break
            if sch == 27:
                self.draw_pad()
                return
            if sch == 127:
                search_string = search_string[:-1]
            else:
                search_string += chr(sch)
            self.draw_pad(search_term=search_string)
        if sch != 27:
            search_string = search_string.replace(" ", "+")
            self.query(search_string)
            self.draw_pad()

    def query(self, search_string):
        subprocess.Popen([self.cmd, self.search_engine + search_string],
                         shell=False)


class ListPad():

    def __init__(self, cmd, item_list, names, color_pair, flags=None,
                 arg_prepend=None, arg_post=None):
        self.cmd = cmd
        if flags:
            self.flags = flags
        else:
            self.flags = []
        if arg_prepend:
            self.arg_prepend = arg_prepend
        else:
            self.arg_prepend = ""
        if arg_post:
            self.arg_post = arg_post
        else:
            self.arg_post = ""
        self.item_list = item_list
        self.names = names
        self.selection = 0
        self.pad = curses.newpad(len(item_list) + 100,
                                 len(item_list) + 100)
        self.pad.bkgd(color_pair)
        self.scroll = 0

    def draw_pad(self, v_scroll, h_scroll, y1, x1, y2, x2):
        self.pad.erase()
        self.pad.prefresh(v_scroll, h_scroll, y1, x1, y2, x2)

    def spawn(self):
        subprocess.Popen([self.cmd] + self.flags +
                         [(self.arg_prepend + self.item_list[self.selection]
                           + self.arg_post)],
                         shell=False)


class Menu():

    def __init__(self, rc_path):
        self.rc_path = rc_path
        self.active = 0
        self.pads = []
        self.titles = []
        self.load_rc(rc_path)

    def get_largest_string(self, string_list):
        largest_string = 0
        for string in string_list:
            if len(string) > largest_string:
                largest_string = len(string)
        return largest_string

    def get_largest_list(self):
        largest_list = 0
        lists = [pad.item_list for pad in self.pads]
        for list_ in lists:
            if len(list_) > largest_list:
                largest_list = len(list_)
        return largest_list

    def get_dimensions(self):
        rows, cols = os.popen('stty size', 'r').read().split()
        self.rows = int(rows)
        self.cols = int(cols)

    def load_rc(self, rc_path):
        with open(rc_path) as jfile:
            rc = json.load(jfile)
        self.fg = rc["fg"]
        self.bg = rc["bg"]
        self.screen, self.rows, self.cols = curses_init(self.fg, self.bg)
        pads = rc["pads"]
        for pad in pads.keys():
            if len(pads[pad]["items"]) != len(pads[pad]["names"]):
                raise RuntimeError(
                    "Items and names must be the same. Check json rc file.")
                exit(1)
            self.titles.append(str(pad))
            self.pads.append(ListPad(pads[pad]["command"],
                                     pads[pad]["items"],
                                     pads[pad]["names"],
                                     curses.color_pair(1),
                                     flags=pads[pad]["flags"],
                                     arg_prepend=pads[pad]["arg_prepend"],
                                     arg_post=pads[pad]["arg_post"]))
        self.largest_list = self.get_largest_list()
        if self.largest_list > self.rows//2:
            self.largest_list = self.rows//2
        browser = rc["browser"]
        search_engine = rc["search_engine"]
        self.search_pad = SearchPad(self.rows//2 - self.largest_list//2 - 2,
                                    self.cols//5,
                                    3*self.cols//5,
                                    browser, search_engine, curses.color_pair(2))

    def draw_statics(self):
        for num, title in enumerate(self.titles):
            self.screen.addstr(self.rows//2 - self.largest_list//2,
                               (num + 1) * self.cols//(len(self.pads) + 1) -
                               len(title)//2,
                               title)
        self.screen.refresh()

    def draw_datetime(self):
        now = datetime.now()
        date_and_time = now.strftime("%d/%m/%Y  -  %H:%M:%S")
        self.screen.addstr(self.rows//2 - self.largest_list//2 - 4,
                           self.cols//2 - len(date_and_time)//2, date_and_time)

    def draw_active(self, highlight=True):
        self.pads[self.active].pad.erase()
        for num, item in enumerate(self.pads[self.active].names):
            if self.pads[self.active].selection == num and highlight == True:
                self.pads[self.active].pad.addstr(num, 0, ">")
            self.pads[self.active].pad.addstr(num, 3, item)
            if len(self.pads[self.active].names) > self.rows//2:
                scroll = max(
                    0, self.pads[self.active].selection - self.rows//2 + 1)
                self.pads[self.active].pad.refresh(scroll, 0,
                                                   self.rows//2 - self.largest_list//2 + 2,
                                                   ((self.active + 1) * self.cols//(len(self.pads) + 1)
                                                    - self.cols//(len(self.pads) + 4)),
                                                   self.rows//2 + self.largest_list//2 + 2,
                                                   ((self.active + 2) * self.cols//(len(self.pads) + 1)
                                                       - 2 - self.cols//(len(self.pads) + 4)))
            else:
                self.pads[self.active].pad.refresh(0, 0,
                                                   self.rows//2 - self.largest_list//2 + 2,
                                                   ((self.active + 1) * self.cols//(len(self.pads) + 1)
                                                    - self.cols//(len(self.pads) + 4)),
                                                   self.rows//2 + self.largest_list//2 + 2,
                                                   ((self.active + 2) * self.cols//(len(self.pads) + 1)
                                                       - 2 - self.cols//(len(self.pads) + 4)))

    def draw_all_pads(self):
        self.screen.refresh()
        self.search_pad.draw_pad()
        for num in range(len(self.pads)):
            self.active = num
            self.draw_active(highlight=False)
        self.active = 0


def main_loop():
    tui_loop(os.getenv("HOME")+"/.konbini.json")
