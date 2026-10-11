# Plagiarism detection

The assignment directory should contain one folder per student directly at the top level (e.g. `alice/`, `bob/`), since the first path component is used as the student's name.

How to use:

```
find . -name "*.py" | python plagi.py
```

Will compare all python files for each user and compare them to all others. 

## Feature-based version

Put the path to the assignment directory in `features/ROOT_DIR`, and add one file per feature in `features/` containing a single shell command (typically a `grep -r`) that is run from that directory and prints matching paths. Then, from the repository root, run:

```
python plagi_feature.py
```

Each student gets a 0/1 vector marking which features their name appears in the output of, sorted by how many features they match. Here the student name is the part of each top-level entry before the first `_`.
