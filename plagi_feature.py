import os
import glob
import subprocess

ROOT_DIR_FILE = "features/ROOT_DIR"

class Person:
    def __init__(self, name, anon=False):
        self.anon = anon
        self.name = name
        self.feature_vector = []

class Feature:
    def __init__(self, command):
        self.command = command

    def execute(self):
        res = subprocess.run(self.command, shell=True, capture_output=True)
        return res.stdout.decode('utf-8')

if __name__ == "__main__":
    feature_files = glob.glob("features/*")
    feature_files.remove(ROOT_DIR_FILE)
    features = []
    people = []
    for feature in feature_files:
        with open(feature) as f:
            features.append(Feature(f.readline().strip()))
    with open(ROOT_DIR_FILE) as f:
        root_dir = f.readline().strip()
        os.chdir(root_dir)

    for line in glob.glob("*"):
        name = line.split("_")[0]
        if name not in [x.name for x in people]:
            people.append(Person(name))

    for feature in features:
        result = feature.execute()
        for person in people:
            if person.name in result:
                person.feature_vector.append(1)
            else:
                person.feature_vector.append(0)

    for person in sorted(people, key=lambda x: sum(x.feature_vector)):
        print(f"{person.name} - {person.feature_vector} - {sum(person.feature_vector)}")
