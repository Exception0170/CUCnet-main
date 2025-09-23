from flask import Flask,render_template
from getservice import check_multiple_services 
import json
from datetime import datetime
app=Flask(__name__)

def load_news():
	try:
		with open('news.json', 'r', encoding='utf-8') as f:
			news_list = json.load(f)
			# Sort by timestamp (newest first)
			news_list.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
			return news_list
	except FileNotFoundError:
		return []
	
@app.route('/')
def index():
	news_list = load_news()[:7]
	return render_template('index.html',title='main', news_list=news_list)

@app.route('/news')
def news_page():
    news_list = load_news()  # Get all news
    return render_template('news.html', news_list=news_list)

@app.route('/status')
def status():
	services_status=check_multiple_services([['ngircd','IRC'],['wg-quick@wg0','Network']],[['python3 bot.py','Telegram Bot']])
	active_count=sum(1 for service in services_status if service['state']=='Active')
	return render_template('status.html',title='status',services=services_status,active=active_count,total=len(services_status))

@app.route('/about')
def about():
	return render_template('about.html',title='About CUCnet')
@app.route('/contacts')
def contacts():
	return render_template('contacts.html',title='Contacts')
@app.route('/guides')
def guides():
	return render_template('guides.html',title='Guides')
@app.route('/guides/irc')
def irc():
	return render_template('guides/irc.html',title='IRC Guide')
@app.route('/guides/connect')
def connect():
	return render_template('guides/connect.html',title="Conenct Guide")
@app.errorhandler(404)
def page_not_found(e):
	return render_template('404.html',title="Not found"),404
if __name__=='__main__':
	app.run(debug=True, host='0.0.0.0',port=8000)

