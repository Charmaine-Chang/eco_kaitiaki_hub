import pymysql

try:
    conn = pymysql.connect(
        host="127.0.0.1",
        user="root",
        password="521200cq",
        database="eco_kaitiaki_hub",
        port=3306
    )

    print("Connected successfully!")

    conn.close()

except Exception as e:
    print(type(e))
    print(repr(e))