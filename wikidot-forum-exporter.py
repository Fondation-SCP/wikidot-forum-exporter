# Wikidot forum exporter
# By: Cyrielle Centori
# Still unoptimized and not really convenient to use, I’ll improve it… eventually.
from bs4 import BeautifulSoup
import requests
import json
from multiprocessing import Pool
from multiprocessing import Lock
import multiprocessing
import sys

def flatten_list(nested_list):
    flattened_list = []
    for item in nested_list:
        if isinstance(item, list):
            flattened_list.extend(flatten_list(item))
        else:
            flattened_list.append(item)
    return flattened_list

# Recursive function needed to keep messages indentations
def parse_fpc(fpc):
	posts = fpc.find_all(class_="post")
	containers = fpc.find_all(class_="post_container")
	ret_list = []
	for post in posts:
		title = str(post.find(class_="long").find(class_="head").find(class_="title").string)
		info = post.find(class_="long").find(class_="head").find(class_="info")
		author = "(account deleted)"
		try: # If account deleted, generates an IndexError
			author = str(info.find(class_="printuser").find_all("a")[1].string)
		except IndexError:
			pass
		date = str(info.find(class_="odate").string)
		content = post.find(class_="long").find(class_="content").prettify()
		ret_list.append({"title" : title, "author" : author, "date" : date, "content" : content})
	for container in containers:
		ret_list.append(parse_fpc(container))
	return ret_list

# Parse a thread
# Has to be in a separate function to use multiprocessing
def parse_thread(thread):
	print("Thread:", thread["title"])
	url = thread["url"]
	try:
		r = requests.get(url, allow_redirects=True)
	except Exception as e:
		print("Error in thread", thread["title"], "retrying.")
		return parse_thread(thread)
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
			try:
				r = requests.get(thread["url"] + "/p/" + str(page), allow_redirects=True)
			except Exception as e:
				print("Error in thread", thread["title"], "retrying.")
				return parse_thread(thread)
			thread_page = BeautifulSoup(r.content, "html.parser")
		tcp = thread_page.find(id="thread-container-posts")
		for fpc in tcp.find_all(class_="post-container", recursive=False):
			message_groups.append(parse_fpc(fpc)) # This part needs recursivity
	return message_groups
	
# Parse a category in multiple pages
def parse_category(i, category):
	page = i + 1
	try:
		r = requests.get(category["url"] + "/p/" + str(page), allow_redirects=True)
	except Exception as e:
		print("Error in category", category["name"], "retrying.")
		return parse_category(i, category)
	cat_page = BeautifulSoup(r.content, "html.parser")
	threads = cat_page.find(class_="table").find_all("tr")[1::]
	ret = []
	for thread in threads:
		title = str(thread.find(class_="name").find(class_="title").a.string)
		url = (site + thread.find(class_="name").find(class_="title").a.get("href")).rsplit("/", 1)[0]
		description = str(thread.find(class_="name").find(class_="description").string)
		date = str(thread.find(class_="started").find(class_="odate").string)
		posts = int(thread.find(class_="posts").string)
		author = "Wikidot/account deleted"
		try: # Page discussions have "Wikidot" as authors. Might also be a deleted account; I’m too lazy to make the difference.
			author = str(thread.find(class_="started").find(class_="printuser").find_all("a")[1].string)
		except IndexError:
			pass
		ret.append({"title" : title, "url" : url, "description" : description, "author" : author, "date" : date, "posts" : posts})
	return ret

# Put Wikidot site here
site = "http://fondationscp.wikidot.com"

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
		name = str(link_html.string)
		url = (site + link_html.get("href")).rsplit("/", 1)[0]
		threads = int(link.find(class_="threads").string)
		posts = int(link.find(class_="posts").string)
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
	
	p = Pool(processes=multiprocessing.cpu_count())
	threads_data = flatten_list(p.starmap(parse_category, [(k, category) for k in range(pages)]))
	
	category["threads"] = threads_data
	
	print("Threads found:", len(threads_data))
	print("Parsing messages…")
	
	p = Pool(processes=multiprocessing.cpu_count())
	message_groups_list = p.imap(parse_thread, threads_data)
	
	for (thread, message_group) in list(zip(threads_data, message_groups_list)):
		thread["messages"] = message_group
	
	p.close()
	p.join()
	
json_output = json.dumps(categories, indent=4)
with open("output.json", "w") as outfile:
	outfile.write(json_output)
