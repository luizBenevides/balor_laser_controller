import os
import psycopg2
from psycopg2 import extras
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

class DBManager:
    def __init__(self):
        self.conn_params = {
            "host": os.getenv("DB_HOST"),
            "port": os.getenv("DB_PORT"),
            "database": os.getenv("DB_NAME"),
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASS"),
            "connect_timeout": 5
        }
        self.connection = None

    def connect(self):
        """Estabelece conexão com o banco de dados PostgreSQL."""
        try:
            if self.connection is None or self.connection.closed:
                self.connection = psycopg2.connect(**self.conn_params)
                print(f"[DB] Conectado ao banco {self.conn_params['database']} em {self.conn_params['host']}")
            return True
        except Exception as e:
            print(f"[DB] Erro ao conectar: {e}")
            return False

    def disconnect(self):
        """Fecha a conexão com o banco de dados."""
        if self.connection:
            self.connection.close()
            self.connection = None

    def get_pending_serials(self):
        """
        Busca seriais aprovados (resultado = 'A') do tipo 'estanque' 
        que ainda não foram gravados pela laser.
        """
        if not self.connect():
            return []

        try:
            with self.connection.cursor(cursor_factory=extras.DictCursor) as cur:
                query = """
                    SELECT id, serial, criado_em 
                    FROM logs_producao 
                    WHERE resultado = 'A' 
                      AND test_type = 'estanque' 
                      AND laser_gravado = FALSE
                    ORDER BY criado_em ASC
                """
                cur.execute(query)
                return cur.fetchall()
        except Exception as e:
            print(f"[DB] Erro ao buscar seriais: {e}")
            return []

    def mark_as_engraved(self, log_id):
        """
        Marca um registro como gravado pela laser no banco de dados.
        """
        if not self.connect():
            return False

        try:
            with self.connection.cursor() as cur:
                query = """
                    UPDATE logs_producao 
                    SET laser_gravado = TRUE, 
                        laser_data_gravacao = CURRENT_TIMESTAMP 
                    WHERE id = %s
                """
                cur.execute(query, (log_id,))
                self.connection.commit()
                print(f"[DB] Registro ID {log_id} marcado como GRAVADO.")
                return True
        except Exception as e:
            print(f"[DB] Erro ao atualizar status: {e}")
            if self.connection:
                self.connection.rollback()
            return False

if __name__ == "__main__":
    # Teste de conexão usando as variáveis do .env
    db = DBManager()
    print("Testando conexão com o Raspberry Pi (via .env)...")
    if db.connect():
        print("Conexão OK!")
        pending = db.get_pending_serials()
        print(f"Seriais pendentes encontrados: {len(pending)}")
        for row in pending:
            print(f"ID: {row['id']} | Serial: {row['serial']}")
        db.disconnect()
    else:
        print("Não foi possível conectar. Verifique seu arquivo .env e se o IP está acessível.")
