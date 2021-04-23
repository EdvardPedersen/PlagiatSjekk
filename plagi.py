import sys
import os
import pathlib
import ast
from collections import defaultdict
import re

IDENTICAL_LIMIT = 0.0001
SIMILARITY_LIMIT = 0.2

class Person:
    def __init__(self, name):
        self.name = name
        self.files = []
        self.asts = []
        self.manual_flag = False
        self.error_log = []
        self.others = {}
        self.patterns = []
        self.patterns.append(re.compile("'.*'"))
        self.patterns.append(re.compile("\".*\""))
        self.patterns.append(re.compile("n\=.*\)"))

    def add_file(self, filename):
        if "/venv/" not in filename:
            self.files.append(filename)

    def generate_ast(self):
        for f in self.files:
            try:
                with open(f) as cur_file:
                    self.asts.append(ast.parse(cur_file.read(), filename=f))
            except Exception as e:
                print(e)
                self.manual_flag = True
                self.error_log.append(e)

    def combine_ast(self):
        text = defaultdict(int)
        for element in self.asts:
            for sub_element in ast.walk(element):
                t = ast.dump(sub_element)
                for pattern in self.patterns:
                    t = re.sub(pattern, "", t)
                text[t] = 1
        self.operations = text
        self.operation_count = sum(self.operations.values())

    def compare_other(self, other):
        ''' returns a originality value, closer to 0 = less original '''
        difference = 0
        for key in self.operations:
            if key not in other.operations:
                difference += 1
        for key in other.operations:
            if key not in self.operations:
                difference += 1
        total_difference = (difference/max(self.operation_count,1))
        self.others[other.name] = total_difference
        #other.others[self.name] = total_difference

        return difference/max(self.operation_count,1)

    def get_summary(self):
        if self.manual_flag:
            return
        results = []
        for name in sorted(self.others, key=lambda x: self.others[x]):
            if self.others[name] < IDENTICAL_LIMIT:
                print(f"{self.name} - {name} - in a group")
            elif self.others[name] < SIMILARITY_LIMIT:
                results.append(f"{self.name} - {name} : {self.others[name]}")
        return results


if __name__ == "__main__":
    all_paths = []
    for line in sys.stdin:
        shortline = line.strip()
        all_paths.append(os.path.normpath(shortline))

    names = {}
    for path in sorted(all_paths):
        name = path.split("/")[0]
        if name not in names:
            names[name] = Person(name)
        names[name].add_file(path)
    print("Got all paths")

    num = 0
    for name in names:
        print(f"Generating ASTs for {name}")
        names[name].generate_ast()
        num += 1
    print("Generated ASTs")

    for name in names:
        names[name].combine_ast()

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
    for name in names:
        r = names[name].get_summary()
        if r:
            results[name] = r

    for result in results:
        for s in results[result]:
            print(s)

    for name in names:
        if names[name].manual_flag:
            print(f"{name} needs manual verification")
