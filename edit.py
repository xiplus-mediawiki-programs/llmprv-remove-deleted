# -*- coding: utf-8 -*-
import argparse
import json
import os
import re
import time

os.environ['PYWIKIBOT_DIR'] = os.path.dirname(os.path.realpath(__file__))
import pywikibot
from pywikibot.data.api import Request
from config import config_page_name  # pylint: disable=E0611,W0614

parser = argparse.ArgumentParser()
parser.add_argument('--confirm', action='store_true')
parser.add_argument('--dry-run', action='store_true', help='只顯示差異，不儲存')
parser.set_defaults(confirm=False)
args = parser.parse_args()

os.environ['TZ'] = 'UTC'

print('Run at', time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()))

site = pywikibot.Site()
site.login()

config_page = pywikibot.Page(site, config_page_name)
cfg = config_page.text
cfg = json.loads(cfg)
print(json.dumps(cfg, indent=4, ensure_ascii=False))

if not cfg["enable"]:
    print('disabled')
    exit()

cvpage = pywikibot.Page(site, cfg["page_name"])
text = cvpage.text

sections = re.split(r'^(?====.*=== *$)', text, flags=re.M)

removedcnt = 0
remaincnt = 0
istimeout = False
for secid, section in enumerate(sections[1:], 1):
    title, _, text = section.partition('\n')
    print(title, end="\t")

    text = re.split(r"^(?=.*{{LLMPRVEntry\|)", text, flags=re.M)

    entrycnt = len(text[1:])
    print(entrycnt)

    newtext = title + '\n' + text[0]
    cnt = 0
    for entry in text[1:]:
        m = re.search(r"{{LLMPRVEntry\|1=([^|]+)\|time=(\d+)(\||}})", entry)
        if m:
            pagename = m.group(1)
            entrytime = int(m.group(2))
            print("\t", pagename, entrytime, end="\t")
            if entrytime > time.time():
                istimeout = True
                print("timeout", end="\t")
            page = pywikibot.Page(site, pagename)
            remove = False
            if not page.exists():
                data = Request(site=site, parameters={
                    'action': 'query',
                    'letitle': pagename,
                    "list": "logevents",
                    "leprop": "comment",
                    "letype": "delete",
                    "lelimit": "1"
                }).submit()
                if len(data['query']['logevents']) > 0:
                    print(data['query']['logevents'][0]['comment'])
                    remove = True

            if remove:
                cnt += 1
            else:
                if not istimeout:
                    remaincnt += 1
                print("not remove")
                newtext += entry
        else:
            print("not match")
            newtext += entry

    if cnt == entrycnt:
        print("\t*** remove {} entry and section".format(cnt))
        sections[secid] = ''
    elif cnt > 0:
        print("\t*** remove {} entry".format(cnt))
        sections[secid] = newtext

    removedcnt += cnt

    if istimeout:
        break

text = ''.join(sections)

if cvpage.text == text:
    print('nothing changed')
    exit()

if args.dry_run or args.confirm:
    pywikibot.showDiff(cvpage.text, text)
cvpage.text = text
summary = cfg["page_summary"].format(removedcnt, remaincnt)
print(summary)
if args.dry_run:
    print('dry run, not saved')
    exit()
if args.confirm:
    save = input('Save?').lower()
else:
    save = 'yes'
if save in ['yes', 'y', '']:
    cvpage.save(summary=summary, minor=False)
