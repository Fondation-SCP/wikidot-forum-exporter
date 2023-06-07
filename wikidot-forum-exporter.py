# Wikidot forum exporter
# By: Cyrielle Centori
# Still unoptimized and not really convenient to use, I’ll improve it… eventually.
from bs4 import BeautifulSoup
import requests
import json

# Recursive function needed to keep messages indentations
def parse_fpc(fpc):
	posts = fpc.find_all(class_="post")
	containers = fpc.find_all(class_="post_container")
	ret_list = []
	for post in posts:
		title = post.find(class_="long").find(class_="head").find(class_="title").string
		info = post.find(class_="long").find(class_="head").find(class_="info")
		author = "(account deleted)"
		try: # If account deleted, generates an IndexError
			author = info.find(class_="printuser").find_all("a")[1].string
		except IndexError:
			pass
		date = info.find(class_="odate").string
		content = post.find(class_="long").find(class_="content").prettify()
		ret_list.append({"title" : title, "author" : author, "date" : date, "content" : content})
	for container in containers:
		ret_list.append(parse_fpc(container))
	return ret_list

# Put Wikidot site here
site = "http://commandemento5.wikidot.com"

#r = requests.get(site + "/forum:start", allow_redirects=True) # Without hidden threads
r = requests.get(site + "/forum/start/hidden/show", allow_redirects=True) # With hidden threads
html_page = BeautifulSoup(r.content, "html.parser")
groups = html_page.find_all("div", class_="forum-group")

print("Parsing forum categories…")

categories = []
for group in groups:
	links = group.find_all("tr")[1::]
	for link in links:
		link_html = link.find(class_="name").find(class_="title").a
		name = link_html.string
		url = (site + link_html.get("href")).rsplit("/", 1)[0]
		threads = link.find(class_="threads").string
		posts = link.find(class_="posts").string
		categories.append({"name" : name, "url" : url, "threads" : threads, "posts" : posts})


print("Categories found:", len(categories))
print("Parsing threads…")

for category in categories:
	print("Category:", category["name"])
	url = category["url"]
	r = requests.get(url, allow_redirects=True)
	cat_page = BeautifulSoup(r.content, "html.parser")
	pages = 1
	try: # Gets the number of pages. If there is only one page, there is no page counter: IndexError, pages keeps the value "one"
		pages = int(cat_page.find_all(class_="pager")[0].span.string.split(" ")[-1])
	except IndexError:
		pass
	
	threads_data = []
	
	for i in range(pages):
		page = i + 1
		if page != 1: # No need to get the page again
			r = requests.get(category["url"] + "/p/" + str(page), allow_redirects=True)
			cat_page = BeautifulSoup(r.content, "html.parser")
		threads = cat_page.find(class_="table").find_all("tr")[1::]
		for thread in threads:
			title = thread.find(class_="name").find(class_="title").a.string
			url = (site + thread.find(class_="name").find(class_="title").a.get("href")).rsplit("/", 1)[0]
			description = thread.find(class_="name").find(class_="description").string
			date = thread.find(class_="started").find(class_="odate").string
			posts = int(thread.find(class_="posts").string)
			author = "Wikidot/account deleted"
			try: # Page discussions have "Wikidot" as authors. Might also be a deleted account; I’m too lazy to make the difference.
				author = thread.find(class_="started").find(class_="printuser").find_all("a")[1].string
			except IndexError:
				pass
			threads_data.append({"title" : title, "url" : url, "description" : description, "author" : author, "date" : date, "posts" : posts})
	category["threads"] = threads_data
	
	print("Thread found:", len(threads_data))
	print("Parsing messages…")
	
	for thread in threads_data:
		print("Thread:", thread["title"])
		url = thread["url"]
		r = requests.get(url, allow_redirects=True)
		thread_page = BeautifulSoup(r.content, "html.parser")
		pages = 1
		try:
			pages = int(thread_page.find_all(class_="pager")[0].span.string.split(" ")[-1])
		except IndexError:
			pass
		
		message_groups = [] # A message is stored in a group.
		
		for i in range(pages):
			page = i + 1
			if page != 1:
				r = requests.get(thread["url"] + "/p/" + str(page), allow_redirects=True)
				thread_page = BeautifulSoup(r.content, "html.parser")
			tcp = thread_page.find(id="thread-container-posts")
			for fpc in tcp.find_all(class_="post-container", recursive=False):
				message_groups.append(parse_fpc(fpc)) # This part needs recursivity
		thread["messages"] = message_groups

json_output = json.dumps(categories, indent=4)
with open("output.json", "w") as outfile:
	outfile.write(json_output)
