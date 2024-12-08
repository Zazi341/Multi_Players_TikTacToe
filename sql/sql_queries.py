CREATE_USER_SQL = """
CREATE TABLE IF NOT EXISTS users (
    username_id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    token VARCHAR(255) NOT NULL
)
"""

CREATE_LEADERBOARD_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS leaderboard (
    leaderboard_id INT PRIMARY KEY AUTO_INCREMENT,
    username_id INT NOT NULL,
    wins INT NOT NULL DEFAULT 0,
    losses INT NOT NULL DEFAULT 0,
    draws INT NOT NULL DEFAULT 0,
    FOREIGN KEY (username_id) REFERENCES users (username_id)
)
"""

CREATE_GAME_TABLE_SQL = """
   CREATE TABLE IF NOT EXISTS games (
       game_id INT PRIMARY KEY AUTO_INCREMENT,
       username_id INT NOT NULL,
       result VARCHAR(255) NOT NULL,
       timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       FOREIGN KEY (username_id) REFERENCES users (username_id)
   )
   """
