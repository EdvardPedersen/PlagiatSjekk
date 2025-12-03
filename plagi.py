import sys
import os
import pathlib
import ast
from collections import defaultdict
import re
import syntaxtree
import statistics
import argparse
import random

IDENTICAL_LIMIT = 0.0001
# Limit of similarity expressed as a multiple of the standard deviation
DEVIATION_MOD = 1.7

class Person:
    def __init__(self, name, out_file = None):
        self.name = name
        self.files = []
        self.asts = syntaxtree.SyntaxTree("")
        self.manual_flag = False
        self.error_log = []
        self.others = {}
        self.patterns = []
        self.patterns.append(re.compile("'.*'"))
        self.patterns.append(re.compile("\".*\""))
        self.patterns.append(re.compile("n\=.*\)"))
        self.out_file = out_file

    def add_file(self, filename):
        if "/venv/" not in filename and "MACOSX" not in filename:
            self.files.append(filename)

    def generate_ast(self):
        for f in self.files:
            try:
                if f[-3:] == ".py":
                    self.asts += syntaxtree.generate_ast_py(f)
                elif f[-2:] == ".c":
                    self.asts += syntaxtree.generate_ast_clang(f)
            except Exception as e:
                print(e)
                self.manual_flag = True
                self.error_log.append(e)


    def compare_other(self, other):
        res = self.asts.compare(other.asts, 1, 2)
        self.others[other.name] = res
        return res

    def get_summary(self, stdev, mean):
        if self.manual_flag:
            return
        results = []
        for name in sorted(self.others, key=lambda x: self.others[x]):
            if self.others[name] < IDENTICAL_LIMIT:
                print(f"{self.name} - {name} - in a group")
            elif self.others[name] < (mean - (stdev * DEVIATION_MOD)):
                results.append(f"{self.name} - {name} : {self.others[name]}")
            if self.out_file:
                self.out_file.write(f"{self.name}|{name}|{self.others[name]}\n")
        return results


if __name__ == "__main__":
    parse = argparse.ArgumentParser()
    parse.add_argument('-f')
    parse.add_argument('-a', action='store_true')
    args = parse.parse_args()
    f = None
    if args.f:
        f = open(args.f, 'w+')

    all_paths = []
    for line in sys.stdin:
        shortline = line.strip()
        all_paths.append(os.path.normpath(shortline))

    real_names = {}
    names = {}
    name_count = 0
    for path in sorted(all_paths):
        name = path.split("/")[0]
        if name not in real_names:
            if args.a:
                real_names[name] = name_count
            else:
                real_names[name] = name
            names[real_names[name]] = Person(real_names[name], f)
            name_count += 1
        names[real_names[name]].add_file(path)
    print("Got all paths")

    num = 0
    for name in names:
        print(f"Generating ASTs for {name}")
        names[name].generate_ast()
        num += 1
    print("Generated ASTs")


    for i in range(len(names)):
        name = list(names.keys())[i]
        if names[name].manual_flag:
            continue
        for j in range(i+1, len(names)):
            name2 = list(names.keys())[j]
            if names[name2].manual_flag:
                continue
            if name == name2:
                continue
            similarity = names[name].compare_other(names[name2])
    results = {}

    all_diff = []

    for n in names:
        all_diff.extend(names[n].others.values())
    mean_all = statistics.mean(all_diff)
    stdev_all = statistics.pstdev(all_diff)

    for name in names:
        r = names[name].get_summary(stdev_all, mean_all)
        if r:
            results[name] = r


    for result in results:
        for s in results[result]:
            print(s)

    for name in names:
        if names[name].manual_flag:
            print(f"{name} needs manual verification")

    print(f"Mean: {mean_all}\nStdev: {stdev_all}")
