TOKEN = "token"

EMBED_COLOR = 0xE44C65

WEBHOOK_ID = 1234567890
WEBHOOK_TOKEN = "webhook_token"

IPC_SECRET_KEY = "ipc_secret_key"
IPC_STANDARD_PORT = 10003
IPC_MULTICAST_PORT = 20003

COMMUNITY_GUILD_ID = 1234567890

DB_NAME = "db_name"
DB_USER = "db_user"
DB_PASSWORD = "db_password"
DB_HOST = "localhost"
DB_PORT = 3306

MUSIC_NODES = [
    {
        "identifier": "node_id",
        "ssl": False,
        "host": "localhost",
        "port": 2333,
        "password": "node_password",
    }
]

TOPGG_TOKEN = "topgg_token"

INITIAL_EXTENSIONS = [
    "cogs.__dev__",
    "cogs.__error__",
    "cogs.__eval__",
    "cogs.__ipc__",
    "cogs.__topgg__",
    "cogs.filters",
    "cogs.general",
    "cogs.help",
    "cogs.music",
    "cogs.utility",
]
