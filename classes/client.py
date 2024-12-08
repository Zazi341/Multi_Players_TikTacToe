import json
import socket
import threading
import time
import tkinter as tk
from tkinter import messagebox, simpledialog
from typing import NamedTuple

HOST = '127.0.0.1'
PORT = 65432
FORMAT = "utf-8"
ADDR = (HOST, PORT)
MOVE_TIMEOUT = 1000
DATABASE_FILE = "tictactoe.db"
SQL_PATH = ""


class Move(NamedTuple):
    row: int
    col: int
    label: str = ""


class Player(NamedTuple):
    label: str
    color: str


DEFAULT_PLAYERS = (
    Player(label="X", color="blue"),
    Player(label="O", color="green"),
    Player(label="X", color="pink"),
    Player(label="O", color="brown"),
    Player(label="X", color="yellow"),
)


class TicTacToeClient:
    def __init__(self):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.username = None
        self.token = None
        self.num_players = 2  # New variable to store the number of players
        self.create_authentication_window()

    def create_authentication_window(self):
        self.client_socket.connect((HOST, PORT))
        self.root = tk.Tk()
        self.root.title("Tic Tac Toe - Client")
        login_button = tk.Button(self.root, text="Login", command=self.login)
        register_button = tk.Button(self.root, text="Register", command=self.register)
        exit_button = tk.Button(self.root, text="Exit", command=self.exit_game)

        login_button.pack(pady=10)
        register_button.pack(pady=10)
        exit_button.pack(pady=10)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            self.exit_game()

    def register(self):
        self.username = simpledialog.askstring("Register", "Enter your username:")
        if self.username:
            password = simpledialog.askstring("Register", "Enter your desired password:", show='*')
            if password:
                try:
                    self.send_data(f"register {self.username} {password}")
                    # Receive the authentication result from the server
                    response = self.receive_data()
                    if response == "success":
                        self.username = self.receive_data()
                        # self.token = self.receive_data()  # Set the token after a successful registration
                        messagebox.showinfo("Registration Successful", "You have successfully registered.")
                        self.show_game_options()
                    elif response == "exists":
                        messagebox.showwarning("Registration Failed", "Username already exists. Try a different one.")

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to connect to server: {e}")
            else:
                messagebox.showwarning("Invalid Password", "Please enter a valid password.")
        else:
            messagebox.showwarning("Invalid Username", "Please enter a valid username.")

    def login(self):
        self.username = simpledialog.askstring("Login", "Enter your username:")
        if self.username:
            try:
                # Prompt the user for a password
                password = simpledialog.askstring("Login", "Enter your password:", show='*')
                # Send both username and password to the server for authentication
                self.send_data(f"login {self.username} {password}")
                # Receive the authentication result from the server
                auth_result = self.receive_data()

                if auth_result == "success":
                    # self.username = self.receive_data()  # Receive the token after successful login
                    # self.root.destroy()  # Close login window
                    self.show_game_options()
                elif auth_result == "failure":
                    messagebox.showerror("Authentication Failed", "Invalid username or password. Try again.")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to connect to server: {e}")
        else:
            messagebox.showwarning("Invalid Username", "Please enter a valid username.")

    def show_game_options(self):

        # Create a new window for game options
        self.game_options_window = tk.Toplevel()
        self.game_options_window.title("Game Options")

        create_game_button = tk.Button(self.game_options_window, text="Create New Game", command=self.create_game)
        join_game_observer_button = tk.Button(self.game_options_window, text="Join Existing Game As Observer",
                                              command=self.join_game_observer)
        exit_button = tk.Button(self.game_options_window, text="Exit", command=self.exit_game)
        join_available_games_button = tk.Button(self.game_options_window, text="Join Available Game",
                                                command=self.show_available_games)
        join_available_games_button.pack(pady=10)
        create_game_button.pack(pady=10)
        join_game_observer_button.pack(pady=10)
        exit_button.pack(pady=10)

    def create_game(self):
        try:
            num_players = 1
            while num_players is None or num_players not in [2, 3, 4, 5]:
                num_players = simpledialog.askinteger("Number of Players", "Enter the number of players (2 to 5):")
                self.num_players = num_players
            username = self.username
            self.send_data(f"create_game {num_players} {username}")
            response = self.receive_data()
            if response and response.startswith("Game created! Your game ID:"):
                game_id = response.split(":")[1].strip()
                self.show_game_window(game_id, num_players)
            else:
                messagebox.showinfo("Game Creation Failed", response)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect to the server: {e}")

    def show_available_games(self):
        try:
            # Send a request to the server to get a list of available games
            self.send_data("get_available_games")
            # Receive the list of available games from the server
            available_games_str = self.receive_data()

            if available_games_str:
                # Add debugging print statements
                print(f"Received available_games_str: {available_games_str}")
                chosen_game_id = simpledialog.askstring("Join Game", f"Choose a Game ID:\n{available_games_str}")
                # Check if the user selected a game
                if chosen_game_id:
                    self.join_game(chosen_game_id)
            else:
                print("There are currently no games available.")
                messagebox.showwarning("Sorry:( ", "There are currently no games available.")
                return None

        except Exception as e:
            print(f"Error in show_available_games: {e}")
            messagebox.showerror("Error", f"Failed to retrieve available games: {e}")

    def get_available_games(self):
        try:
            self.send_data("get_available_games")
            available_games_str = self.receive_data()

            # Add error handling to check if available_games_str is not None
            if available_games_str:
                available_games = json.loads(available_games_str)
                return available_games
            else:
                print("Received empty or None response for available games.")
                return None

        except Exception as e:
            print(f"Failed to get available games: {e}")
            return None

    def join_game(self, game_id):
        try:
            # Pass the client's username along with the game_id
            self.send_data(f"join_game {game_id} {self.username}")

            # Receive the join result from the server
            result = self.receive_data()

            if result.startswith("Joined game successfully!"):
                # messagebox.showinfo("Game Joined", result)
                # פירוק המחרוזת לרכיביה
                parts = result.split(',')
                # הסרת השורה החדשה מהאלמנט האחרון אם יש צורך
                parts[-1] = parts[-1].strip()
                game_id = parts[1]
                num_players_str = parts[-2]

                if num_players_str is not None:
                    try:
                        num_players = int(num_players_str)
                        print(f"num_players_str {num_players}")
                        game_board = self.receive_data()
                        # Parse the string into a dictionary
                        game_board_dict = json.loads(game_board)

                        # Access the game board list of lists
                        game_board = game_board_dict["game_board"]
                        self.show_game_window(game_id, num_players,game_board=game_board)
                    except ValueError:
                        print(f"Failed to convert num_players_str to int: {num_players_str}")
                else:
                    print("Received None for num_players_str.")

            else:
                messagebox.showerror("Join Game Failed", result)

        except Exception as e:
            print(f"Failed to connect to server: {e}")
            messagebox.showerror("Error", f"Failed to connect to server: {e}")

    def join_game_observer(self):
        try:
            # Send a request to the server to get a list of available games
            self.send_data("get_all_available_games")
            # Receive the list of available games from the server
            all_available_games_str = self.receive_data()
            # Add error handling to check if available_games_str is not None
            if all_available_games_str:
                # Add debugging print statements
                print(f"Received all_available_games_str: {all_available_games_str}")

                # Check if the received data is an error message
                if all_available_games_str.startswith("Error"):
                    # Handle the error condition (e.g., display an error message)
                    print(f"Error in join_game_observer: {all_available_games_str}")
                    messagebox.showerror("Error", all_available_games_str)
                    return

                chosen_game_id = simpledialog.askstring("Join Game", f"Choose a Game ID:\n{all_available_games_str}")

                # Check if the user selected a game
                if chosen_game_id:
                    self.join_observer(chosen_game_id)
            else:
                print("There are currently no games available.")
                messagebox.showwarning("Sorry:( ", "There are currently no games available.")
                return None

        except Exception as e:
            print(f"Error in join_game_observer: {e}")
            messagebox.showerror("Error", f"Failed to retrieve available games: {e}")

    def join_observer(self, game_id):
        try:
            # Send a request to the server to join the selected game as an observer
            self.send_data(f"observer_join_game {game_id} observer_{self.username}")
            result = self.receive_data()
            if result.startswith("Joined game successfully!"):
                # messagebox.showinfo("Game Joined", result)
                # פירוק המחרוזת לרכיביה
                parts = result.split(',')
                # הסרת השורה החדשה מהאלמנט האחרון אם יש צורך
                parts[-1] = parts[-1].strip()
                game_id = parts[1]
                num_players_str = parts[-2]

                if num_players_str is not None:
                    try:
                        num_players = int(num_players_str)
                        print(f"num_players_str {num_players}")
                        game_board = self.receive_data()
                        # Parse the string into a dictionary
                        game_board_dict = json.loads(game_board)

                        # Access the game board list of lists
                        game_board = game_board_dict["game_board"]
                        self.show_game_window(game_id, num_players, game_board=game_board)
                    except ValueError:
                        print(f"Failed to convert num_players_str to int: {num_players_str}")
                else:
                    print("Received None for num_players_str.")

            else:
                messagebox.showerror("Join Game Failed", result)

        except Exception as e:
            print(f"Failed to connect to server: {e}")
            messagebox.showerror("Error", f"Failed to connect to server: {e}")


    def exit_game(self):
        self.close_gui_windows()
        # Send a message to the server indicating the client wants to exit
        self.send_data(f"exit_game {self.username}")
        # Add a short delay to allow the server to process the message
        time.sleep(1)

        print("Exiting game. Goodbye!")
        # Close all open GUI windows
        self.client_socket.close()

    def close_gui_windows(self):
        # Close all Tkinter Toplevel windows
        for window in self.root.winfo_children():
            if isinstance(window, tk.Toplevel) and self.root.winfo_exists():
                try:
                    window.destroy()
                except tk.TclError:
                    # Handle the case when the window is already destroyed
                    pass
        self.root.destroy()

    def send_data(self, message):
        try:
            self.client_socket.send(message.encode(FORMAT))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send data to server: {e}")

    def receive_data(self):
        try:
            return self.client_socket.recv(1024).decode(FORMAT, errors='ignore')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to receive data from server: {e}")

    def periodic_update(self):
        while True:
            try:
                threading.Event().wait(2)

            except Exception as e:
                # Handle exceptions if needed
                print(f"Error during periodic update: {e}")

    def show_game_window(self, game_id, num_players, game_board=None):
        self.game_id = game_id
        self.num_players = num_players
        self.game_window = tk.Toplevel()
        self.game_window.title(f"Tic Tac Toe - Game: {game_id}")
        self.player_info_label = tk.Label(self.game_window, text=f"Player Name:{self.username}")
        self.player_info_label.grid(row=0, column=0)
        self.turn_label = tk.Label(self.game_window, text="Current Turn:")
        self.turn_label.grid(row=1, column=0)
        self.board_label = tk.Label(self.game_window, text="Current Game Board:")
        self.board_label.grid(row=2, column=0)
        num_rows = num_columns = (num_players + 1)
        self.board_buttons = [[None for _ in range(num_columns)] for _ in range(num_rows)]

        for row in range(num_rows):
            for col in range(num_columns):
                # Explicitly set the values for row and col before using them in lambda
                button = tk.Button(self.game_window, text="", width=5, height=2,
                                   command=lambda r=row, c=col: self.make_move(r, c))
                button.grid(row=row + 3, column=col)
                self.board_buttons[row][col] = button

        if game_board:
            for i, row in enumerate(game_board):
                for j, cell_value in enumerate(row):
                    button = self.board_buttons[i][j]
                    button.config(text=cell_value)  # Update the button text to show the player's mark
                    button['state'] = 'normal' if cell_value == ' ' else 'disabled'  # Disable played cells

        self.move_entry = tk.Entry(self.game_window, width=5)
        self.move_entry.grid(row=num_rows + 3, column=0)
        # self.move_button = tk.Button(self.game_window, text="Make Move", command=self.make_move)
        # self.move_button.grid(row=num_rows + 3, column=1)
        exit_button = tk.Button(self.game_window, text="Exit Game", command=self.exit_game)
        exit_button.grid(row=num_rows + 3, column=2)
        threading.Thread(target=self.listen_for_server_messages, daemon=True).start()

    def make_move(self, row, col):
        move = f"{row},{col}"
        # Send the move to the server
        self.send_data(f"make_move {self.game_id} {self.username} {move}")
        threading.Thread(target=self.listen_for_server_messages, daemon=True).start()


    def listen_for_server_messages(self):
        while True:
            try:
                message = self.receive_data()
                if message:
                    self.process_server_message(message)
            except Exception as e:
                print(f"Error receiving server message: {e}")
                break

    def process_server_message(self, message):

        # Attempt to parse the message as JSON
        try:
            data = json.loads(message)

            # Process the JSON data
            if 'game_board' in data:  # Handle game board update
                game_board = data['game_board']
                # Run on main thread
                self.game_window.after(0, lambda: self.update_game_board_ui(game_board))
            # Add more conditions as necessary, e.g., handling turn notifications, game results, etc.

        # If a ValueError is caught, it means json.loads() could not parse the message as JSON
        # In this case, it's probably a plain string message
        except ValueError:
            # Show the message in a message box on the main thread
            self.game_window.after(0, lambda: messagebox.showinfo("Server Message", message))

    def update_game_board_ui(self, game_board):
        def task():
            for i, row in enumerate(game_board):
                for j, cell_value in enumerate(row):
                    button = self.board_buttons[i][j]
                    button.config(text=cell_value)  # Update the button text to show the player's mark
                    button['state'] = 'normal' if cell_value == ' ' else 'disabled'  # Disable played cells

        # Schedule the UI update to run on the main thread
        self.game_window.after(0, task)

    def display_game_state(self, game_state):
        # Display the current game state, including player information and board
        game_state_dict = json.loads(game_state)
        # Update player information label
        player_info_text = f"Player: {game_state_dict['current_player']}\n"
        player_info_text += f"Your Mark: {game_state_dict['player_mark']}\n"
        player_info_text += f"Opponent's Mark: {game_state_dict['opponent_mark']}"
        self.player_info_label.config(text=player_info_text)
        # Update the turn label
        turn_text = f"Current Turn: {game_state_dict['current_player']}'s turn"
        self.turn_label.config(text=turn_text)
        # Update the game board
        self.board_label.config(text=game_state_dict['board'])

    def update_game_state_after_join(self):
        # Retrieve and display the current game state
        game_state = self.receive_data()
        self.display_game_state(game_state)



if __name__ == "__main__":
    client = TicTacToeClient()
    client.root.mainloop()
