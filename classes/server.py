import json
import socket
import threading

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from enums.game import Game
from sql.SQLClient import SQLClient
from utils.utils import generate_token

HOST = '127.0.0.1'
PORT = 65432
FORMAT = "utf-8"
ADDR = (HOST, PORT)
MOVE_TIMEOUT = 10000
DATABASE_FILE = "tictactoe.db"
SQL_PATH = ""
key = b'\x04\x03|\xeb\x8dSh\xe0\xc5\xae\xe5\xe1l9\x0co\xca\xb1"\r-Oo\xbaiYa\x1e\xd1\xf7\xa2\xdf'
iv = b'#\xb59\xee\xa7\xc4@n\xe5r\xac\x97lV\xff\xf1'


class TicTacToeServer:
    def __init__(self, num_players=2):
        self.username = None
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.num_players = num_players
        self.players_chars = ['X', 'O', '∆', '4', '5']
        self.players = self.players_chars[:num_players]
        self.board_size = num_players + 1
        self.current_player = self.players[0]
        self.players_tokens = {}
        self.user_data = {}
        self.leaderboard_data = {}
        self.games_data = {}
        self.sql_client = SQLClient()
        self.load_all_data()

    def load_all_data(self):
        self.user_data = self.sql_client.load_user_data()
        self.leaderboard_data = self.sql_client.load_leaderboard_data()
        self.games_data = self.sql_client.load_games_data()

    def handle_client(self, conn, token):
        conn.settimeout(MOVE_TIMEOUT)  # Set the timeout for receiving moves
        try:
            while True:
                try:
                    move = conn.recv(1024).decode(FORMAT, errors='ignore')
                    if not move:
                        break
                    if move.startswith("make_move"):
                        parts = move.split()
                        game_id = parts[1]
                        username = parts[-2]  # נניח שהשם משתמש מועבר כחלק מהפקודה
                        row_col_part = parts[-1]
                        row_str, col_str = row_col_part.split(',')
                        row, col = int(row_str), int(col_str)

                        # בדיקה אם זה תור השחקן
                        if not self.is_players_turn(game_id, username):
                            conn.send("It's not your turn.\n".encode(FORMAT))
                            continue

                        # ממשיך כרגיל אם זה תור השחקן
                        if self.games_data[game_id][Game.BOARD][row][col] == ' ':
                            current_player = self.games_data[game_id][Game.CURRENT_PLAYER]
                            self.games_data[game_id][Game.BOARD][row][col] = self.players_chars[current_player]
                            self.send_game_board_to_all_clients(game_id)
                            if self.check_win(self.players_chars[current_player], game_id):
                                win_message = f"Congratulations! Player {username} wins the game!"
                                self.broadcast_to_all_clients_in_game(win_message, game_id)
                                self.sql_client.update_leaderboard(username, 'win')

                                losers_list = self.games_data[game_id][Game.PLAYERS]
                                del losers_list[username]
                                for loser in losers_list:
                                    self.sql_client.update_leaderboard(loser, 'loss')

                                self.sql_client.load_leaderboard_data()

                            elif self.check_tie(game_id):
                                tie_message = "It's a tie!"
                                self.broadcast_to_all_clients_in_game(tie_message, game_id)

                                draw_users_list = self.games_data[game_id][Game.PLAYERS]
                                for draw_user in draw_users_list:
                                    self.sql_client.update_leaderboard(draw_user, 'draw')

                                self.sql_client.load_leaderboard_data()
                            else:
                                self.get_next_player(game_id)
                                current_player = self.games_data[game_id][Game.CURRENT_PLAYER]
                                # player_turn_message = f"Your move, player {current_player}.\n"
                                # self.broadcast_to_all_clients_in_game(player_turn_message, game_id)

                        else:
                            conn.send("Invalid move. Try again.\n".encode(FORMAT))

                    if move.startswith("register "):
                        reg_username, reg_password = move.split()[1:]
                        registration_result = self.sql_client.insert_user(reg_username, reg_password)
                        if registration_result:
                            conn.send("success".encode(FORMAT))
                            conn.send(registration_result.encode(FORMAT))
                        else:
                            conn.send("failure".encode(FORMAT))
                        continue

                    if move.startswith("login "):
                        login_username, login_password = move.split()[1:]
                        login_result, message = self.sql_client.authenticate_user(login_username, login_password)
                        if login_result:
                            conn.send(message.encode(FORMAT))
                        else:
                            conn.send(message.encode(FORMAT))
                        continue

                    # Check if the received message is for changing the number of players
                    if move.startswith("set_players "):
                        new_num_players = move.split()
                        if new_num_players not in [2, 3, 4, 5]:
                            conn.send("Invalid number of players. Please enter 2 or 3 or 4 or 5.\n".encode(FORMAT))
                        else:
                            self.set_num_players(new_num_players)
                            conn.send(f"Number of players updated to {new_num_players}.\n".encode(FORMAT))
                        continue

                    if move.startswith("exit_game"):
                        try:
                            # Extract the username from the message
                            username = move.split()[1]
                        except IndexError:
                            print("Invalid format for exit_game message.\n")
                            continue

                        print(username)
                        self.remove_player_from_game(username)
                        break

                    if move.startswith("create_game"):
                        try:
                            num_players, cr_username = move.split()[1:]
                            num_players = int(num_players)
                        except ValueError:
                            conn.send("Invalid format for create_game message.\n".encode(FORMAT))
                            continue

                        response = self.create_game(num_players, cr_username, conn)
                        conn.send(response.encode(FORMAT))
                        continue

                    if move.startswith("get_available_games"):
                        # Get the list of available games and send it to the client
                        available_games = self.get_available_games()
                        games_str = ' '.join(available_games)  # Convert the list to a space-separated string
                        conn.send(games_str.encode(FORMAT))
                        continue

                    if move.startswith("get_all_available_games"):
                        # Get the list of available games and send it to the client as a JSON string
                        all_available_games = self.get_all_available_games()
                        games_str = json.dumps(all_available_games)
                        conn.send(games_str.encode(FORMAT))
                        continue

                    if move.startswith("join_game"):
                        try:
                            # Extract the game ID from the message
                            game_id, username = move.split()[1:]
                            # Implement the logic to join the game using the game ID
                            # You might want to check if the game exists and if the player can join
                            # Example:
                            if game_id in self.games_data:
                                game_data = self.games_data[game_id]
                                num_players = game_data[Game.NUM_PLAYERS]
                                print(num_players)
                                players_in_game = game_data[Game.PLAYERS]

                                if len(players_in_game) < num_players:
                                    # Add the player to the game
                                    game_data[Game.PLAYERS].append(username)
                                    game_data[Game.PLAYERS_AND_SPECTATORS_CONNECTIONS].append(conn)

                                    conn.send(f"Joined game successfully!,{game_id},{num_players},.\n".encode(FORMAT))
                                    # self.notify_spectators(f"Player {username} has joined game {game_id}.\n", game_id)
                                    # self.send_game_board_to_all_clients(game_id)

                                    game_board = self.games_data[game_id][Game.BOARD]  # Get the game board data
                                    game_board_json = json.dumps({'game_board': game_board})
                                    conn.send(game_board_json.encode('utf-8'))

                                    # Update the game state and send it to the client
                                else:
                                    conn.send(f"Game {game_id} is full. Cannot join.\n".encode(FORMAT))
                            else:
                                conn.send(f"Game {game_id} does not exist.\n".encode(FORMAT))

                        except IndexError:
                            conn.send("Invalid format for join_game message.\n".encode(FORMAT))
                        continue  # Continue the loop after processing the join_game message

                    if move.startswith("observer_join_game"):
                        game_id, username = move.split()[1:]
                        # Implement the logic to join the game using the game ID
                        # You might want to check if the game exists and if the player can join
                        # Example:
                        if game_id in self.games_data:
                            game_data = self.games_data[game_id]
                            num_players = game_data[Game.NUM_PLAYERS]
                            game_data[Game.PLAYERS_AND_SPECTATORS_CONNECTIONS].append(conn)
                            conn.send(f"Joined game successfully!,{game_id},{num_players},.\n".encode(FORMAT))
                            # self.notify_spectators(f"Player {username} has joined game {game_id}.\n", game_id)

                            game_board = self.games_data[game_id][Game.BOARD]  # Get the game board data
                            game_board_json = json.dumps({'game_board': game_board})
                            conn.send(game_board_json.encode('utf-8'))



                except socket.timeout:
                    conn.send("Timeout: No move received within the time limit. Game aborted.\n".encode(FORMAT))
                    self.sql_client.update_leaderboard(self.current_player, 'loss')
                    self.sql_client.load_leaderboard_data()


        except Exception as e:
            print(f"Error in handle_client: {e}")
            conn.send(f"Error: {e}\n".encode(FORMAT))

        finally:
            if token in self.players_tokens:
                del self.players_tokens[token]

            try:
                conn.send("Server closing connection.\n".encode(FORMAT))
            except:
                pass  # The connection may already be closed by the client

        print("connection with a client closed")
        conn.close()

    def get_available_games(self):
        try:
            available_games = [game_id for game_id, game_data in self.games_data.items()
                               if len(game_data['players']) < game_data['num_players']]
            print(f"Available games: {available_games}")
            return available_games

        except Exception as e:
            print(f"Error in get_available_games: {e}")
            return None

    def get_all_available_games(self):
        try:
            all_available_games = [game_id for game_id, game_data in self.games_data.items()]
            print(f"Available games: {all_available_games}")
            return all_available_games

        except Exception as e:
            print(f"Error in get_available_games: {e}")
            return None

    def create_game(self, num_players, username, user_connection):
        try:
            print(f"Received username: {username}, num_players: {num_players}")
            # Check if the user is already in a game
            for game_id, game_data in self.games_data.items():
                if username in game_data['players']:
                    return "You are already in a game. Finish or exit the current game before creating a new one."

            if int(num_players) not in [2, 3, 4, 5]:
                return "Invalid number of players. Please enter 2, 3, 4, or 5."

            game_id = generate_token()

            self.games_data[game_id] = {
                Game.GAME_ID: game_id,
                Game.NUM_PLAYERS: int(num_players),
                Game.PLAYERS: [username],
                Game.BOARD: [[' ' for _ in range((int(num_players) + 1))] for _ in
                             range((int(num_players) + 1))],
                Game.CURRENT_PLAYER: 0,
                Game.SPECTATORS: [],
                Game.PLAYERS_AND_SPECTATORS_CONNECTIONS: [user_connection]
            }
            return f"Game created! Your game ID: {game_id} Num Players: {num_players}"

        except Exception as e:
            return f"Error creating the game: {e}"

    def set_num_players(self, num_players):
        self.num_players = num_players
        players_chars = ['X', 'O', '∆', '4', '5']
        self.players = players_chars[:num_players]
        self.row_column_size = (num_players + 1)
        self.current_player = self.players[0]

    def check_win(self, player_symbol, game_id):
        board = self.games_data[game_id][Game.BOARD]
        board_size = len(board)

        # Check rows and columns for 3 in a row of the player's symbol
        for i in range(board_size):
            for j in range(board_size - 2):
                if board[i][j] == board[i][j + 1] == board[i][j + 2] == player_symbol:
                    return True
                if board[j][i] == board[j + 1][i] == board[j + 2][i] == player_symbol:
                    return True

        # Check diagonals for player's symbol
        for i in range(board_size - 2):
            if board[i][i] == board[i + 1][i + 1] == board[i + 2][i + 2] == player_symbol:
                return True
            if board[i][board_size - 1 - i] == board[i + 1][board_size - 2 - i] == board[i + 2][
                board_size - 3 - i] == player_symbol:
                return True

        return False

    def check_tie(self, game_id):
        board = self.games_data[game_id][Game.BOARD]
        # Check if any cell in the board is still empty (indicating the game is not yet a draw)
        for row in board:
            if ' ' in row:  # Assuming ' ' represents an empty cell
                return False

        # If no cell is empty and no player has won, it's a draw
        return True

    def get_next_player(self, game_id):
        # Retrieve the current player index
        current_index = self.games_data[game_id][Game.CURRENT_PLAYER]

        # Retrieve the list of players
        num_players = self.games_data[game_id][Game.NUM_PLAYERS]

        # Increment the index to get the next player
        # The modulo operator (%) wraps the index around if it goes past the end of the list
        next_index = (current_index + 1) % num_players

        # Update the game data with the index of the next player
        self.games_data[game_id][Game.CURRENT_PLAYER] = next_index

        # Return the username of the next player
        return next_index

    def is_players_turn(self, game_id, username):
        # קבלת האינדקס של השחקן הנוכחי
        current_player_index = self.games_data[game_id][Game.CURRENT_PLAYER]
        # קבלת השם של השחקן הנוכחי מתוך רשימת השחקנים
        if (0 <= current_player_index < len(self.games_data[game_id][Game.PLAYERS])):
            current_player_name = self.games_data[game_id][Game.PLAYERS][current_player_index]
            return current_player_name == username

        else:
            return False

        # השוואה בין השם שקיבלנו לשם שרוצים לבדוק

    def notify_spectators(self, message, game_id):
        # Retrieve the game data using the game_id
        game_data = self.games_data.get(game_id)

        # Check if the game data exists
        if game_data:
            # Retrieve the list of spectators for the specified game
            spectators = game_data.get(Game.SPECTATORS, [])

            # Loop through each spectator and send them the message
            for spectator in spectators:
                try:
                    spectator.send(message.encode('utf-8'))  # Assuming 'utf-8' as the FORMAT
                except Exception as e:
                    print(f"Error sending message to spectator: {e}")
                    # Optionally, handle the exception (e.g., logging or removing the spectator from the list)
        else:
            print(f"No game data found for game_id: {game_id}")

    def remove_player_from_game(self, username):
        # Iterate through all games and remove the player
        for game_id, game_data in self.games_data.items():
            if username in game_data[Game.PLAYERS]:
                game_data[Game.PLAYERS].remove(username)
                # Notify other players/spectators about the player's exit
                self.notify_spectators(f"Player {username} has left game {game_id}.\n")
                # If the game is now empty, remove it from game data
                if not game_data[Game.PLAYERS]:
                    del self.games_data[game_id]
                    print(f"Game {game_id} removed from game data.")
                    break  # Exit the loop after removing the player from the game and the game is now empty
                else:
                    print(f"Player {username} removed from game {game_id}.")
                    break  # Exit the loop after removing the player from the game

    def send_game_board_to_all_clients(self, game_id):
        """Serialize the game board to JSON and send it to all connected clients."""
        game_board = self.games_data[game_id][Game.BOARD]  # Get the game board data
        # Serialize the game board here only once
        game_board_json = json.dumps({'game_board': game_board})
        self.broadcast_to_all_clients_in_game(game_board_json, game_id)

    def broadcast_to_all_clients_in_game(self, game_board_json, game_id):
        """Send a JSON-formatted message with the game board to all players and spectators in a game."""
        if game_id in self.games_data:
            connections = self.games_data[game_id][Game.PLAYERS_AND_SPECTATORS_CONNECTIONS]
            failed_connections = []  # To track connections that fail to receive the message

            for conn in connections:
                try:
                    # Send the JSON string as it is
                    conn.send(game_board_json.encode('utf-8'))
                except Exception as e:
                    failed_connections.append(conn)
                    # Handle the failed connections as needed

            # Remove failed connections if any
            for conn in failed_connections:
                connections.remove(conn)
                # Further handling for the disconnected clients

    # def broadcast_to_specific_client_in_game(self, game_id, connection):
    #     game_board = self.games_data[game_id][Game.BOARD]  # Get the game board data
    #     # Serialize the game board here only once
    #     game_board_json = json.dumps({'game_board': game_board})
    #     conn.send(game_board_json.encode('utf-8'))

    def broadcast_a_message_to_all_clients_in_game(self, game_board_message, game_id):
        """Send a regular string message with the game board to all players and spectators in a game."""
        if game_id in self.games_data:
            connections = self.games_data[game_id]['players_and_spectators_connections']
            failed_connections = []  # To track connections that fail to receive the message

            for conn in connections:
                try:
                    # Send the string message as it is
                    conn.send(game_board_message.encode('utf-8'))  # Assuming the connection send method accepts strings
                except Exception as e:
                    failed_connections.append(conn)
                    # Handle the failed connections as needed

            # Remove failed connections if any
            for conn in failed_connections:
                connections.remove(conn)
                # Further handling for the disconnected clients

    def start_server(self):
        self.server_socket.bind(ADDR)
        print(f"[LISTENING] Server is listening on {HOST}:{PORT}")
        self.server_socket.listen()

        while True:
            connection, address = self.server_socket.accept()
            print(f"[NEW CONNECTION] {address} connected.")
            # Generate a unique token for the client
            token = generate_token()
            self.players_tokens[token] = connection
            # Start the client thread
            client_thread = threading.Thread(target=self.handle_client, args=(connection, token))
            client_thread.start()


if __name__ == '__main__':
    server = TicTacToeServer()
    server.start_server()
