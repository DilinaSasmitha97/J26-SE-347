Profile photos for the demo users.

Drop a square-ish JPG here using the filename that matches the account:

  admin.jpg     -> Dewmini Navodya  (admin@askdb.io,  owner)
  viewer.jpg    -> Sara Lewis       (viewer@askdb.io, viewer)

Any file missing here simply falls back to the user's coloured initials,
so the app works fine with none, some, or all of them present.

Filenames are set per user in server/src/store.js (the avatarUrl field).
