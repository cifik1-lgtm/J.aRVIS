import sqlite3
from pathlib import Path
import sys

def sql_interactor(parameters: dict, player=None) -> str:
    action = parameters.get("action", "query")
    db_path_str = parameters.get("db_path", "")
    query = parameters.get("query", "")
    
    if not db_path_str:
        return "You must specify a db_path (e.g. C:\\my_db.sqlite). If the file doesn't exist, it will be automatically created."
        
    db_path = Path(db_path_str).expanduser().resolve()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        if action == "query" or action == "execute":
            if not query: return "No SQL query provided."
            cursor.execute(query)
            
            if query.strip().upper().startswith(("SELECT", "PRAGMA")):
                rows = cursor.fetchall()
                cols = [desc[0] for desc in cursor.description] if cursor.description else []
                conn.close()
                if not rows: return "Query executed successfully. 0 rows returned."
                
                res = f"Results ({len(rows)} rows):\n"
                res += " | ".join(cols) + "\n"
                res += "-" * 40 + "\n"
                for i, row in enumerate(rows[:50]):
                    res += " | ".join(str(x) for x in row) + "\n"
                if len(rows) > 50:
                    res += f"... and {len(rows)-50} more rows omitted."
                return res
            else:
                conn.commit()
                conn.close()
                return "Query executed and committed successfully."
                
        elif action == "list_tables":
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            conn.close()
            if not tables: return "No tables found in the database."
            return "Tables in DB: " + ", ".join(t[0] for t in tables)
            
        elif action == "schema":
            table = parameters.get("table", "")
            if not table: return "No table provided for schema."
            cursor.execute(f"PRAGMA table_info('{table}');")
            info = cursor.fetchall()
            conn.close()
            if not info: return f"Table '{table}' not found in the database."
            res = f"Schema for table '{table}':\n"
            for col in info:
                res += f"- {col[1]} ({col[2]})\n"
            return res
            
        return "Unknown SQL action."
    except Exception as e:
        return f"SQL Error: {e}"
