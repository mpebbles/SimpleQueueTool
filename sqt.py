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
        if len(color) == 0:
            return text
        elif '\n' in text:
            return "\n".join([self.colors[color] + x + self.end for x in text.splitlines()])
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
        self.c.execute('''CREATE TABLE IF NOT EXISTS queue_info
                          (id INTEGER PRIMARY KEY AUTOINCREMENT,
                           queue_name text NOT NULL,
                           color text NOT NULL DEFAULT ''
                          );''')
        # create table for items mapping to colors
        self.c.execute('''CREATE TABLE IF NOT EXISTS items
                          (id INTEGER PRIMARY KEY AUTOINCREMENT,
                           queue_id INTEGER NOT NULL,
                           title text NOT NULL,
                           priority INTEGER NOT NULL,
                           description text,
                           time_requirement INTEGER,
                           FOREIGN KEY(queue_id) REFERENCES queue_info(id)
                           ON DELETE CASCADE
                          );''')
        self.conn.commit()

    def create_queue(self, *args):
        if args[1].isdigit():
            print('Queue name cannot be a number.')
            return
        try:
            if args[1] == "HELP":
                raise Exception
            name_to_create = " ".join(args[1:]) if '--color' != args[-2] else " ".join(args[1:-2])
            # check that value doesn't already exist
            self.c.execute('''SELECT * FROM queue_info WHERE queue_name = ?''', (name_to_create,))
            if self.c.fetchone() is not None:
                print("{} already exists".format(name_to_create))
                return

            # insert value
            if '--color' not in args:
                self.c.execute('''INSERT INTO queue_info(queue_name)
                                VALUES
                                (?)
                              ''', (name_to_create,))
                self.conn.commit()
            elif '--color' in args[-2]:
                if args[-1] not in self.color_ob.colors:
                    colors_str = [x for x in self.color_ob.colors]
                    print("Color not supported. Supported colors: {}".format(", ".join(colors_str)))

                    return
                self.c.execute('''INSERT INTO queue_info(queue_name, color)
                                VALUES
                                (?, ?)
                              ''', (name_to_create,args[-1]))
                self.conn.commit()
            else:
                raise Exception
        except Exception as e:
            print('Usage: create <queue_name> --color color')

    def view(self, *args):
        try:
            if args[1] == "HELP":
                raise Exception
            queue_ref_rows = self.c.execute('''SELECT * FROM queue_info''').fetchall()
            if not len(queue_ref_rows):
                print('There are no queues to view.')
                return
            colors = [x[2] for x in queue_ref_rows]
            formatted_colors = [self.color_ob.color(queue_ref_rows[i][1],x) for i,x in enumerate(colors)]
            output = PrettyTable(formatted_colors)
            queue_items = []
            queue_refs = [x[0] for x in queue_ref_rows]
            for ref in queue_refs:
                rows = self.c.execute('''SELECT * FROM items WHERE
                                         queue_id = ? ORDER BY priority ASC''',(ref,)).fetchall()
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
                    if len(x) > 0:
                        id = x[0][0]
                        priority = x[0][3]
                        title = x[0][2]
                        row_str = "{} - {}\n\tPriority: {}".format(id, title, priority)
                        if len(x[0][4]) > 0:
                            row_str += "\n{}".format(x[0][4])
                        if x[0][5] != 0:
                            row_str += "\n\tTime requirement: {}".format(x[0][5])
                        row.append(self.color_ob.color(row_str, colors[ind]) + "\n\n")
                    else:
                        row.append(self.color_ob.color("--", colors[ind]) + "\n\n")
                if len(row) > 0:
                    output.add_row(row)
                print(output)
            else:
                queue_ref = self.c.execute('''SELECT * FROM queue_info WHERE queue_name = ?''',(" ".join(args[1:]),)).fetchone()
                if not queue_ref:
                    print("Please use 'view all' or 'view top' or 'view <queue_name>)")
                output = PrettyTable([self.color_ob.color(" ".join(args[1:]), queue_ref[2])])
                rows = self.c.execute('''SELECT * FROM items WHERE
                                         queue_id = ? ORDER BY priority ASC''',(queue_ref[0],)).fetchall()
                for x in rows:
                    if len(x) > 0:
                        id = x[0]
                        priority = x[3]
                        title = x[2]
                        row_str = "{} - {}\nPriority: {}".format(id, title, priority)
                        if len(x[4]) > 0:  # description
                            row_str += "\n{}".format(x[4])
                        if x[5] != 0:
                            row_str += "\nTime requirement: {}".format(x[5])
                        output.add_row([self.color_ob.color(row_str, queue_ref[2]) + "\n\n"])
                print(output)
        except Exception as e:
            print("Usage: view < all | top | queue name >")

    def insert(self, *args):
        # user input: insert <queue> : <name> : <priority> [--desc <"desc text"> --time <int>]
        try:
            if args[1] == "HELP":
                raise Exception
            tmp_args = " ".join(args).split(':')
            args = []
            description = ""
            parsing_desc, parsing_time = False, False
            time_requirement = 0
            for arg in tmp_args:
                if len(args):
                    args.append(":")
                tmp_list = arg.split()
                for ind, sub_arg in enumerate(tmp_list):
                    if '--desc' in tmp_list[ind]:
                        parsing_desc = True
                        parsing_time = False
                    elif '--time' in tmp_list[ind]:
                        parsing_time = True
                        parsing_desc = False
                    elif parsing_desc:
                        description += " " + sub_arg
                    elif parsing_time:
                        time_requirement = int(sub_arg)
                        parsing_time = False
                    else:
                        args.append(sub_arg)

            self.c.execute('''SELECT * FROM queue_info WHERE queue_name = ?''', (" ".join(args[1:args.index(':')]),))
            row = self.c.fetchone()
            if row is None:
                print("Invalid queue name.")
                return
            # queue exists
            priority = 100 # TODO: make configurable?
            if args.count(':') == 2:
                priority = int(" ".join(args).split(':')[2])
            name_to_insert = "".join(" ".join(args).split(':')[1])

            self.c.execute('''INSERT INTO items(queue_id,title, priority, description, time_requirement)
                              VALUES
                              (?, ?, ?, ?, ?)
                           ''', (row[0],name_to_insert,priority, description, time_requirement))
            self.conn.commit()
        except Exception as e:
            print("Usage: insert <queue name> : <item name> [: <priority>] [--desc <desc text> --time <int>]")

    def remove(self, *args):
        # user input: remove  [* | queue | item_id]
        try:
            if args[1] == "HELP":
                raise Exception
            elif args[1] == '*':
                user_confirm = input("Are you sure you want to remove everything? y/n: ").lower()
                if not user_confirm.startswith("y"):
                    print("Nothing was removed.")
                    return
                self.c.execute('''DELETE FROM queue_info''')
                print("All queues were removed.")
                return
            elif not args[1].isdigit():
                user_confirm = input("Remove {}? y/n: ".format(args[1])).lower()
                if not user_confirm.startswith("y"):
                    print("{} not removed.".format(args[1]))
                    return
                success = self.c.execute('''DELETE FROM queue_info
                              WHERE queue_name = ?
                              ''', (args[1],))
            else: # delete item from queue
                success = self.c.execute('''DELETE FROM items
                                WHERE id = ?
                                ''', (args[1],))
            if success.rowcount:
                print("{} removed.".format(args[1]))
            else:
                print("Nothing to delete.")
            self.conn.commit()
        except Exception as e:
            print("Usage: remove [ * | queue | item id ]")


    def process_input(self, input):
        try:
            split_input = input.split() if ' ' in input else [input, "HELP"]
            if split_input[0] == 'create':
                self.create_queue(*split_input)
            elif split_input[0] == 'insert':
                self.insert(*split_input)
            elif split_input[0] == 'remove':
                self.remove(*split_input)
            elif split_input[0] == 'help':
                print("\nCommands: create, insert, remove, view, exit.\nType a command with no arguments to view usage info.\n")
            elif split_input[0] == 'view':
                self.view(*split_input)
            elif split_input[0] == 'exit':
                # using boolean to keep I/O error from occurring
                self.exiting = True
                return
            else:
                print("Invalid input.")
        except:
            print("Invalid input. Type help to view commands.")

def main():
    #parser = argparse.ArgumentParser(description='Simple Queue Tool')
    #parser.add_argument('--flag', help='help')
    #prog_args = parser.parse_args()
    conn_str = "/".join(os.path.realpath(__file__).split('/')[:-1]) + "/sqt.db"
    print("******* Simple Queue Tool - A helpful task management tool *******"
          "\nCreated by Mitchell Pebbles.",
          "\nPlease email mitchell.jeffrey.pebbles@gmail.com with any bugs, questions, or requests.",
          "\nType 'help' to view program info.")
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
