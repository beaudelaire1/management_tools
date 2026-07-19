# scheduling (G10)

Resources, bookings and absences with transactional conflict detection.

- `book_resource` locks the resource row; overlapping confirmed bookings and absences are rejected; adjacent slots are allowed.
- Limits: recurrences, preparation time and timezone-per-resource remain to implement.
