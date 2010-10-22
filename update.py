# -*- coding: UTF-8 -*-
#
# update.py - part of the FDroid server tools
# Copyright (C) 2010, Ciaran Gultnieks, ciaran@ciarang.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import os
import shutil
import glob
import subprocess
import re
import zipfile
import md5
from xml.dom.minidom import Document
from optparse import OptionParser

#Read configuration...
execfile('config.py')

# Parse command line...
parser = OptionParser()
parser.add_option("-c", "--createmeta", action="store_true", default=False,
                  help="Create skeleton metadata files that are missing")
(options, args) = parser.parse_args()


icon_dir=os.path.join('repo','icons')

# Delete and re-create the icon directory...
if os.path.exists(icon_dir):
    shutil.rmtree(icon_dir)
os.mkdir(icon_dir)

# Gather information about all the apk files in the repo directory...
apks = []
for apkfile in glob.glob(os.path.join('repo','*.apk')):

    apkfilename = apkfile[5:]

    print "Processing " + apkfilename
    thisinfo = {}
    thisinfo['apkname'] = apkfilename
    p = subprocess.Popen([aapt_path,'dump','badging',
       apkfile], stdout=subprocess.PIPE)
    output = p.communicate()[0]
    if p.returncode != 0:
        print "Failed to get apk information"
        print output
        sys.exit(1)
    for line in output.splitlines():
        if line.startswith("package:"):
            pat = re.compile(".*name='([a-z0-9.]*)'.*")
            thisinfo['id'] = re.match(pat, line).group(1)
            pat = re.compile(".*versionCode='([0-9]*)'.*")
            thisinfo['versioncode'] = re.match(pat, line).group(1)
            pat = re.compile(".*versionName='([^']*)'.*")
            thisinfo['version'] = re.match(pat, line).group(1)
        if line.startswith("application:"):
            pat = re.compile(".*label='([^']*)'.*")
            thisinfo['name'] = re.match(pat, line).group(1)
            pat = re.compile(".*icon='([^']*)'.*")
            thisinfo['iconsrc'] = re.match(pat, line).group(1)

    # Calculate the md5...
    m = md5.new()
    f = open(apkfile, 'rb')
    while True:
        t = f.read(1024)
        if len(t) == 0:
            break
        m.update(t)
    thisinfo['md5'] = m.hexdigest()
    f.close()

    # Extract the icon file...
    apk = zipfile.ZipFile(apkfile, 'r')
    thisinfo['icon'] = (thisinfo['id'] + '.' +
        thisinfo['versioncode'] + '.png')
    iconfilename = os.path.join(icon_dir, thisinfo['icon'])
    iconfile = open(iconfilename, 'wb')
    iconfile.write(apk.read(thisinfo['iconsrc']))
    iconfile.close()
    apk.close()

    apks.append(thisinfo)

# Get all apps...
apps = []

for metafile in glob.glob(os.path.join('metadata','*.txt')):

    thisinfo = {}

    # Get metadata...
    thisinfo['id'] = metafile[9:-4]
    print "Reading metadata for " + thisinfo['id']
    thisinfo['description'] = ''
    thisinfo['summary'] = ''
    thisinfo['license'] = 'Unknown'
    thisinfo['web'] = ''
    thisinfo['source'] = ''
    thisinfo['tracker'] = ''
    thisinfo['disabled'] = None
    f = open(metafile, 'r')
    mode = 0
    for line in f.readlines():
        line = line.rstrip('\r\n')
	if len(line) == 0:
            pass
        elif mode == 0:
            index = line.find(':')
            if index == -1:
                print "Invalid metadata in " + metafile + " at:" + line
                sys.exit(1)
            field = line[:index]
            value = line[index+1:]
            if field == 'Description':
                mode = 1
            elif field == 'Summary':
                thisinfo['summary'] = value
            elif field == 'Source Code':
                thisinfo['source'] = value
            elif field == 'License':
                thisinfo['license'] = value
            elif field == 'Web Site':
                thisinfo['web'] = value
            elif field == 'Issue Tracker':
                thisinfo['tracker'] = value
            elif field == 'Disabled':
                thisinfo['disabled'] = value
            else:
                print "Unrecognised field " + field
                sys.exit(1)
        elif mode == 1:
            if line == '.':
                mode = 0
            else:
                if len(line) == 0:
                    thisinfo['description'] += '\n\n'
                else:
                    if (not thisinfo['description'].endswith('\n') and
                        len(thisinfo['description']) > 0):
                        thisinfo['description'] += ' '
                    thisinfo['description'] += line
    if len(thisinfo['description']) == 0:
        thisinfo['description'] = 'No description available'

    apps.append(thisinfo)

# Some information from the apks needs to be applied up to the application
# level. When doing this, we use the info from the most recent version's apk.
for app in apps:
    bestver = 0 
    for apk in apks:
        if apk['id'] == app['id']:
            if apk['versioncode'] > bestver:
                bestver = apk['versioncode']
                bestapk = apk

    if bestver == 0:
        app['name'] = app['id']
        app['icon'] = ''
        print "WARNING: Application " + app['id'] + " has no packages"
    else:
        app['name'] = bestapk['name']
        app['icon'] = bestapk['icon']

# Generate warnings for apk's with no metadata (or create skeleton
# metadata files, if requested on the command line)
for apk in apks:
    found = False
    for app in apps:
        if app['id'] == apk['id']:
            found = True
            break
    if not found:
        if options.createmeta:
            f = open(os.path.join('metadata', apk['id'] + '.txt'), 'w')
            f.write("License:Unknown\n")
            f.write("Web Site:\n")
            f.write("Source Code:\n")
            f.write("Issue Tracker:\n")
            f.write("Summary:" + apk['name'] + "\n")
            f.write("Description:\n")
            f.write(apk['name'] + "\n")
            f.write(".\n")
            f.close()
            print "Generated skeleton metadata for " + apk['id']
        else:
            print "WARNING: " + apk['apkname'] + " (" + apk['id'] + ") has no metadata"
            print "       " + apk['name'] + " - " + apk['version']  

# Create the index
doc = Document()

def addElement(name, value, doc, parent):
    el = doc.createElement(name)
    el.appendChild(doc.createTextNode(value))
    parent.appendChild(el)

root = doc.createElement("fdroid")
doc.appendChild(root)

apps_inrepo = 0
apps_disabled = 0

for app in apps:

    if app['disabled'] is None:
        apps_inrepo += 1
        apel = doc.createElement("application")
        root.appendChild(apel)

        addElement('id', app['id'], doc, apel)
        addElement('name', app['name'], doc, apel)
        addElement('summary', app['summary'], doc, apel)
        addElement('icon', app['icon'], doc, apel)
        addElement('description', app['description'], doc, apel)
        addElement('license', app['license'], doc, apel)
        addElement('web', app['web'], doc, apel)
        addElement('source', app['source'], doc, apel)
        addElement('tracker', app['tracker'], doc, apel)

        for apk in apks:
            if apk['id'] == app['id']:
                apkel = doc.createElement("package")
                apel.appendChild(apkel)
                addElement('version', apk['version'], doc, apkel)
                addElement('versioncode', apk['versioncode'], doc, apkel)
                addElement('apkname', apk['apkname'], doc, apkel)
                addElement('hash', apk['md5'], doc, apkel)
    else:
        apps_disabled += 1

of = open(os.path.join('repo','index.xml'), 'wb')
output = doc.toxml()
of.write(output)
of.close()

print "Finished."
print str(apps_inrepo) + " apps in repo"
print str(apps_disabled) + " disabled"

