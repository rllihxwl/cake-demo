
import pg8000

class DictCursor:
    def __init__(self, cursor):
        self.cursor = cursor
        self.description = None

    def execute(self, sql, params=None):
        if params is None:
            self.cursor.execute(sql)
        else:
            self.cursor.execute(sql, params)
        self.description = self.cursor.description
        return self

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        return self._to_dict(row)

    def fetchall(self):
        rows = self.cursor.fetchall()
        result = []
        for row in rows:
            result.append(self._to_dict(row))
        return result

    def _to_dict(self, row):
        if self.description is None:
            return row
        names = []
        for item in self.description:
            names.append(item[0])
        data = {}
        i = 0
        while i < len(names):
            data[names[i]] = row[i]
            i = i + 1
        return data

    def close(self):
        self.cursor.close()

class DictConnection:
    def __init__(self, conn):
        self.conn = conn

    def cursor(self):
        return DictCursor(self.conn.cursor())

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

def get_connection():
    return pg8000.connect(
        user='postgres',
        password='1234',
        host='127.0.0.1',
        port=5432,
        database='cake_demo'
    )

def get_dict_connection():
    return DictConnection(
        pg8000.connect(
            user='postgres',
            password='1234',
            host='127.0.0.1',
            port=5432,
            database='cake_demo'
        )
    )
