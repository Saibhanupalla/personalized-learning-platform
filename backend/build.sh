#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Run the database initialization script
# This command will execute the init_db() function from your database.py file
python -c 'import database; database.init_db()'
