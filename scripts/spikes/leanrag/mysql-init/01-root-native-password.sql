-- Make every root account authenticate with mysql_native_password, so upstream's
-- pinned PyMySQL (without `cryptography`) can log in. Runs once, on an empty volume.
ALTER USER 'root'@'%' IDENTIFIED WITH mysql_native_password BY '123';
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '123';
