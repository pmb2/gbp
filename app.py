from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def overview():
    return render_template('overview.html')

@app.route('/content-management')
def content_management():
    return render_template('content-management.html')

@app.route('/knowledge-base')
def knowledge_base():
    return render_template('knowledge-base.html')

@app.route('/analytics')
def analytics():
    return render_template('knowledge-base.html')

@app.route('/notifications')
def notifications():
    return render_template('notifications.html')

if __name__ == '__main__':
    app.run(debug=True)
