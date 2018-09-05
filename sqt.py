import sqlite3
import signal
import argparse
import os
import time
from functools import partial
from prettytable import PrettyTable

class Color:
    def __init__(self):
        self.colors = {
            'black': '\033[30m',
            'red': '\033[31m',
            'green': '\033[32m',
            'orange': '\033[33m',
            'blue': '\033[34m',
            'purple': '\033[35m',
            'cyan': '\033[36m',
            'darkgrey': '\033[90m',
            'lightred': '\033[91m',
            'lightgreen': '\033[92m',
            'yellow': '\033[93m',
            'lightblue': '\033[94m',
            'pink': '\033[95m',
        }
        self.end = '\033[0m'

    def color(self,text, color):
        if '\n' in text:
            return "\n".join([self.colors[color] + x + self.end for x in text.splitlines()])
        else:
            return self.colors[color] + text + self.end

class SQT:

    def __init__(self, conn):
        self.conn = conn
        self.c = conn.cursor()
        self.color_ob = Color()
        # enable cascading
        self.c.execute("PRAGMA foreign_keys = 1")
        self.exiting = False
        # create table for colors if it doesn't exist
        self.c.execute('''CREATE TABLE IF NOT EXISTS color_ref
                          (id INTEGER PRIMARY KEY AUTOINCREMENT,
                           color text NOT NULL
                          );''')
        # create table for items mapping to colors
        self.c.execute('''CREATE TABLE IF NOT EXISTS items
                          (id INTEGER PRIMARY KEY AUTOINCREMENT,
                           color_id INTEGER NOT NULL,
                           title text NOT NULL,
                           priority INTEGER NOT NULL,
                           description text,
                           time_requirement INTEGER,
                           FOREIGN KEY(color_id) REFERENCES color_ref(id)
                           ON DELETE CASCADE
                          );''')
        self.conn.commit()

    def create_colored_queue(self, *args):
        try:
            # check that value doesn't already exist
            self.c.execute('''SELECT * FROM color_ref WHERE color = ?''', (args[1],))
            if self.c.fetchone() is not None:
                print("{} colored queue already exists".format(args[1]))
                return
            # insert value
            self.c.execute('''INSERT INTO color_ref(color)
                              VALUES
                              (?)
                            ''', (args[1],))
            self.conn.commit()
        except Exception as e:
            print('Invalid input. \nUsage: create <color>')

    def view(self, *args):
        try:
            color_ref_rows = self.c.execute('''SELECT * FROM color_ref''').fetchall()
            colors = [x[1] for x in color_ref_rows]
            formatted_colors = [self.color_ob.color(x,x) for x in colors]
            output = PrettyTable(formatted_colors)
            queue_items = []
            color_refs = [x[0] for x in color_ref_rows]
            for ref in color_refs:
                rows = self.c.execute('''SELECT * FROM items WHERE
                                         color_id = ? ORDER BY priority ASC''',(ref,)).fetchall()
                queue_items.append(rows)
            if args[1] == "all":
                # make each queue equal length with "--"
                max_length = len(max(queue_items, key=len))
                for q_item in queue_items:
                    start = len(q_item)
                    for i in range(start,max_length):
                        q_item.append("--")
                for i in range(0, max_length):
                    row = []
                    for ind, x in enumerate(queue_items):
                        if x[i] == "--":
                            row.append(self.color_ob.color("--",colors[ind]) + "\n\n")
                        else:
                            id = x[i][0]
                            priority = x[i][3]
                            title = x[i][2]
                            row_str = "{} - {}\nPriority: {}".format(id, title, priority)
                            if len(x[i][4]) > 0:  # description
                                row_str += "\n{}".format(x[i][4])
                            if x[i][5] != 0:
                                row_str += "\nTime requirement: {}".format(x[i][5])
                            row.append(self.color_ob.color(row_str, colors[ind]) + "\n\n")
                    output.add_row(row)
                print(output)
            elif args[1] == "top":
                row = []
                for ind, x in enumerate(queue_items):
                    id = x[0][0]
                    priority = x[0][3]
                    title = x[0][2]
                    row_str = "{} - {}\n\tPriority: {}".format(id, title, priority)
                    if len(x[0][4]) > 0:
                        row_str += "\n{}".format(x[0][4])
                    if x[0][5] != 0:
                        row_str += "\n\tTime requirement: {}".format(x[0][5])
                    row.append(self.color_ob.color(row_str, colors[ind]) + "\n\n")
                output.add_row(row)
                print(output)
            else:
                output = PrettyTable([self.color_ob.color(args[1], args[1])])
                color_ref = self.c.execute('''SELECT * FROM color_ref WHERE color = ?''',(args[1],)).fetchone()
                if not color_ref:
                    print("Please use 'view all' or 'view top' or 'view <queue>)")
                rows = self.c.execute('''SELECT * FROM items WHERE
                                         color_id = ? ORDER BY priority ASC''',(color_ref[0],)).fetchall()
                for x in rows:
                    id = x[0]
                    priority = x[3]
                    title = x[2]
                    row_str = "{} - {}\nPriority: {}".format(id, title, priority)
                    if len(x[4]) > 0:  # description
                        row_str += "\n{}".format(x[4])
                    if x[5] != 0:
                        row_str += "\nTime requirement: {}".format(x[5])
                    output.add_row([self.color_ob.color(row_str, args[1]) + "\n\n"])
                print(output)
        except Exception as e:
            print("Invalid input.\nUsage: view < all | top | queue_name >")

    def insert(self, *args):
        # user input: insert <queue> <name> <priority> [--desc <"desc text"> --time <int>]
        try:
            desc = ""
            time_requirement = 0
            parsing_desc = False
            parsing_time = False
            if len(args) > 3:
                for arg in args[3:]:
                    if arg == "--desc":
                        parsing_desc = True
                        parsing_time = False
                        continue
                    if arg == "--time":
                        parsing_desc = False
                        parsing_time = True
                        continue
                    if parsing_desc:
                        desc += arg + " "
                    if parsing_time:
                        time_requirement = int(arg)
                # remove quotes if present
                if len(desc) and (desc[0] == '"' or desc[0] == "'") and \
                        (desc[-1] == "'" or desc[-1] == '"'):
                    desc = desc[1:-2]
            self.c.execute('''SELECT * FROM color_ref WHERE color = ?''', (args[1],))
            row = self.c.fetchone()
            if row is None:
                print("Invalid colored queue name.")
                return
            # colored queue exists
            priority = 100 # TODO: make configurable?
            if len(args) > 3 and args[3].isdigit():
                priority = int(args[3])
            self.c.execute('''INSERT INTO items(color_id,title, priority, description, time_requirement)
                              VALUES
                              (?, ?, ?, ?, ?)
                           ''', (row[0],args[2],priority, desc, time_requirement))
            self.conn.commit()
        except Exception as e:
            print("Invalid input.\nUsage: insert <queue> <name> <priority> [--desc <\"desc text\"> --time <int>]")

    def remove(self, *args):
        # user input: remove <queue> [row]
        try:
            if len(args) < 3:
                user_confirm = input("Remove {} queue? y/n: ".format(args[1])).lower()
                if not user_confirm.startswith("y"):
                    print("{} queue not removed.".format(args[1]))
                    return
                self.c.execute('''DELETE FROM color_ref 
                              WHERE color = ?
                              ''', (args[1],))
                print("{} queue removed.".format(args[1]))
            else: # delete item from queue
                self.c.execute('''DELETE FROM items
                                WHERE id = ?
                                ''', (args[2],))
                print("{} removed from {} queue.".format(args[2], args[1]))
            self.conn.commit()
        except Exception as e:
            print("Invalid input.\nUsage: remove <queue> [row]")


    def process_input(self, input):
        try:
            split_input = input.split()
            if split_input[0] == 'create':
                self.create_colored_queue(*split_input)
            elif split_input[0] == 'insert':
                self.insert(*split_input)
            elif split_input[0] == 'remove':
                self.remove(*split_input)
            elif split_input[0] == 'help':
                pass
            elif split_input[0] == 'view':
                self.view(*split_input)
            elif split_input[0] == 'exit':
                # using boolean to keep I/O error from occurring
                self.exiting = True
                return
            else:
                print("Invalid input.")
        except:
            print("Invalid input.") # TODO print help

def main():
    #parser = argparse.ArgumentParser(description='Simple Queue Tool')
    #parser.add_argument('--flag', help='help')
    #prog_args = parser.parse_args()
    conn_str = "/".join(os.path.realpath(__file__).split('/')[:-1]) + "/sqt.db"
    print("Database file: {}".format(conn_str))
    conn = sqlite3.connect(conn_str)

    signal.signal(signal.SIGINT, partial(graceful_exit, conn))
    sqt = SQT(conn)

    while True:
        action = input("sqt>>").lower()
        if len(action):
            sqt.process_input(action)
        if sqt.exiting:
            graceful_exit(conn)


def graceful_exit(conn, *args):
    print("Goodbye.")
    conn.commit()
    conn.close()
    exit()


if __name__ == '__main__':
    main()

# TODO
# document/test better
# make README
# make title --> color mapper and remove color titles
# allow user to make aliases
# implement help
# list dependencies
# put usage in except for each input
# make remove num possible instead of remove <queue> <num>
#  -- require that queues are not named with digits only
