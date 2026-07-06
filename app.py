import os
from PF_LU_APP import create_app

app = create_app()

if __name__ == '__main__':
    app.run(
        debug=os.environ.get('FLASK_DEBUG', '0') == '1',
        port=int(os.environ.get('FLASK_PORT', 5005)),
    )
