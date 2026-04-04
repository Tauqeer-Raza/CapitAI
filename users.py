from database import create_connection

conn = create_connection()
cursor = conn.cursor()

cursor.execute("SELECT * FROM users")
users = cursor.fetchall()

for user in users:
    print(user)

conn.close()