import hashlib
import secrets
import sqlite3
import mysql.connector
from sql.sql_constants import SQLConstants
from sql.sql_queries import *


class SQLClient:
    def __init__(self):
        self.host = SQLConstants.HOST
        self.user = SQLConstants.USER
        self.password = SQLConstants.PASSWORD
        self.database = SQLConstants.DATABASE
        self.conn = self.create_connection()
        self.cur = self.conn.cursor(buffered=True)
        self.create_tables()

    def create_connection(self):
        """Create a database connection."""
        try:
            conn = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database
            )
            if conn.is_connected():
                print("MySQL connection is established.")
                return conn
            else:
                print("Connection failed.")
                return None
        except mysql.connector.Error as e:
            print(f"Error connecting to MySQL database: {e}")
            return None

    def close_connection(self):
        """Close the database connection."""
        if self.conn.is_connected():
            self.conn.close()
            print("MySQL connection is closed.")

    def create_tables(self):
        try:
            self.create_users_table()
            self.create_leaderboard_table()
            self.create_games_table()
            print("Tables created successfully.")
        except sqlite3.Error as e:
            print(f"Error,Tables not created successfully: {e}")
            return None

    def create_games_table(self):
        """Create the games table if it doesn't exist, with a foreign key to the users table."""
        self.cur.execute(CREATE_GAME_TABLE_SQL)
        self.conn.commit()

    def create_users_table(self):
        """Create a placeholder users table for the foreign key relationship."""

        self.cur.execute(CREATE_USER_SQL)
        self.conn.commit()

    def create_leaderboard_table(self):
        """Simulate creating the leaderboard table with a foreign key."""

        self.cur.execute(CREATE_LEADERBOARD_TABLE_SQL)
        self.conn.commit()

    def generate_token(self):
        """Generate a secure random token."""
        return secrets.token_hex(16)

    def insert_user(self, username, password):
        """Insert a new user into the users table with a hashed password and generated token."""
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        token = self.generate_token()
        parameters = (username, hashed_password, token)

        # Check if the username already exists
        self.cur.execute("SELECT username FROM users WHERE username = %s", (username,))
        if self.cur.fetchone():
            # If the username exists, print error and return False
            print(f"Error inserting user: Username {username} already exists.")
            return False

        try:
            self.cur.execute("INSERT INTO users (username, password, token) VALUES (%s, %s, %s)", parameters)
            self.conn.commit()
            print("User inserted successfully.")
            return True
        except mysql.connector.IntegrityError as e:
            print(f"Error inserting user (possible duplicate): {e}")
        except mysql.connector.Error as e:
            print(f"Error inserting user: {e}")
        return False

    def authenticate_user(self, username, password):
        """Authenticate a user with a username and password."""
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        try:
            query = "SELECT password FROM users WHERE username = %s"
            self.cur.execute(query, (username,))
            row = self.cur.fetchone()

            if row:
                stored_password = row[0]
                if stored_password == hashed_password:
                    print("Authentication successful!")
                    return True, "success"
                else:
                    print("Authentication failed: Incorrect password.")
                    return False, "failure"
            else:
                print(f"Authentication failed: Username {username} not found.")
                return False, "failure"
        except sqlite3.Error as e:
            print(f"Database error during authentication: {e}")
            return False, "Database error during authentication."
        except Exception as e:
            print(f"Unexpected error during authentication: {e}")
            return False, "Unexpected error during authentication."

    def close_connection(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            print("SQLite connection is closed.")

    def get_user_id(self, username):
        try:
            # Prepare the SQL query
            query = "SELECT username_id FROM users WHERE username = %s"

            # Execute the SQL query
            self.cur.execute(query, (username,))

            # Fetch the result
            result = self.cur.fetchone()

            # If we have a result, return the username_id
            if result:
                return result[0]  # result[0] is the username_id since it's the only column we selected
            else:
                # Handle the case where the username does not exist
                return None
        except Exception as e:
            print(f"An error occurred: {e}")
            return None

    def update_leaderboard(self, username, result):
        """Increment the user's win, loss, or draw count in the leaderboard based on game result."""
        try:
            # Get the username_id from the username
            username_id = self.get_user_id(username)

            if username_id is None:
                print("User not found.")
                return  # Exit the function if the user is not found

            # Now we have the username_id, we can check if the user exists in the leaderboard
            query = "SELECT wins, losses, draws FROM leaderboard WHERE username_id = %s"
            self.cur.execute(query, (username_id,))
            row = self.cur.fetchone()

            if row:
                # Unpack the current counts
                wins, losses, draws = row
                # Determine which count to increment
                if result == 'win':
                    wins += 1
                elif result == 'loss':
                    losses += 1
                elif result == 'tie':
                    draws += 1
                else:
                    print("Invalid result.")
                    return

                # Update the leaderboard with the new counts
                update_query = "UPDATE leaderboard SET wins = %s, losses = %s, draws = %s WHERE username_id = %s"
                self.cur.execute(update_query, (wins, losses, draws, username_id))
            else:
                # If the user doesn't exist in the leaderboard, create a new record
                wins, losses, draws = (1, 0, 0) if result == 'win' else (0, 1, 0) if result == 'loss' else (
                0, 0, 1) if result == 'tie' else (0, 0, 0)
                if result not in ('win', 'loss', 'tie'):
                    print("Invalid result.")
                    return
                insert_query = "INSERT INTO leaderboard (username_id, wins, losses, draws) VALUES (%s, %s, %s, %s)"
                self.cur.execute(insert_query, (username_id, wins, losses, draws))

            # Commit the changes
            self.conn.commit()
            print(f"Updated {username}'s record: {wins} wins, {losses} losses, {draws} draws.")
        except Exception as e:
            print(f"Error updating leaderboard: {e}")

    def load_leaderboard_data(self):
        """Retrieve leaderboard data or return empty dictionary if error or empty."""
        try:
            # Selecting username_id, wins, losses, and draws from the leaderboard
            query = """
            SELECT username_id, wins, losses, draws
            FROM leaderboard
            ORDER BY wins DESC, draws DESC, losses
            """
            self.cur.execute(query)
            rows = self.cur.fetchall()
            if rows:
                leaderboard_data = [
                    {"username_id": row[0], "wins": row[1], "losses": row[2], "draws": row[3]}
                    for row in rows
                ]
                return {"success": True, "data": leaderboard_data}
            else:
                return {}  # Empty result
        except sqlite3.Error:
            return {}  # Error occurred

    def load_user_data(self):
        """Retrieve user data or return empty dictionary if empty/error."""
        try:
            query = "SELECT username_id, username, token FROM users"
            self.cur.execute(query)
            rows = self.cur.fetchall()
            if rows:
                user_data = [{"username_id": row[0], "username": row[1], "token": row[2]} for row in rows]
                return {"success": True, "data": user_data}
            else:
                return {}  # Empty result
        except sqlite3.Error:
            return {}  # Error occurred

    def load_games_data(self):
        """Retrieve games data or return empty dictionary if empty/error."""
        try:
            query = "SELECT game_id, username_id, result, timestamp FROM games"
            self.cur.execute(query)
            rows = self.cur.fetchall()
            if rows:
                games_data = [{"game_id": row[0], "username_id": row[1], "result": row[2], "timestamp": row[3]} for row in
                              rows]
                return {"success": True, "data": games_data}
            else:
                return {}  # Empty result
        except sqlite3.Error:
            return {}  # Error occurred
