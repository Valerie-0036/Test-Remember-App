## Test Remember App
Simple python app to help you quiz on exams that demands you to remember terminologies and labels of images.

### Terminologies Mode
Upload .csv file, no header just acronym | definition (2 columns, inf rows)

### Labels Mode
Upload .csv file no header just labels, then add image manually. Image can't be moved or renamed, the app refers to the image using the path.

### Other Features
1. Delete test
2. Answers are graded as correct if it have the same answer (disregard capitalization differences)
3. Re-test incorrect answers only
4. Mark answers as unsure

Requirement: PostgreSQL run on 5432 Port