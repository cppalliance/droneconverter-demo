
import yaml
import re
from collections import defaultdict
import hashlib
import inspect
import os
import json

def flatten(something):
    if isinstance(something, (list, tuple, set, range)):
        for sub in something:
            yield from flatten(sub)
    else:
        yield something

from jinja2 import Environment, PackageLoader, select_autoescape
env = Environment(
    loader=PackageLoader('droneconverter', 'templates'),
    autoescape=select_autoescape(['html', 'xml'])
)

cwd = os.path.basename(os.getcwd())

# Ingest .travis.yml

travisyml = defaultdict(dict)
inputfile = open('.travis.yml', 'rt', encoding='latin-1')
travisyml = yaml.load(inputfile, Loader=yaml.FullLoader)
inputfile.close()

# Determine if matrix is stored in "matrix" or "jobs"
matrixlength=0
jobslength=0
if travisyml.get("matrix",{}).get("include"):
    matrixlength=len(travisyml.get("matrix",{}).get("include"))
if travisyml.get("jobs",{}).get("include"):
    jobslength=len(travisyml.get("jobs",{}).get("include"))
if ( jobslength > matrixlength ):
    travisyml["matrix"] = travisyml["jobs"]

if not travisyml.get("matrix",{}).get("include") and not travisyml.get("jobs",{}).get("include"):
    if travisyml.get("os"):
        travisyml["matrix"] = {}
        travisyml["matrix"]["include"] = []
        for operatingsystem in travisyml.get("os"):
            travisyml["matrix"]["include"].append({"os": operatingsystem})
    else:
        print("At least one of 'matrix', 'jobs', or 'os', should be in .travis.yml. Exiting.")
        quit()

# Processing - first stage

# Find the most common "install" and "script". These will be referred to as "boost" later. 
# Other variants will refer to their uuid.

installdictionary=defaultdict(lambda:0)
scriptdictionary=defaultdict(lambda:0)

for i, jobx in enumerate(travisyml["matrix"]["include"]):
    job = travisyml["matrix"]["include"][i]
    # populate defaults into jobs
    for script in ["install", "script", "before_install", "before_script", "after_success"]:
        if not job.get(script):
            if travisyml.get(script):
                job[script] = travisyml[script]
            else:
                job[script] = []

        if isinstance(job[script], bool):
            job[script] = str(job[script]).lower()

    # Error correction: add -y to choco
    for script in ["install","script", "before_install", "before_script", "after_success"]:
        if job.get(script):
            for linenumber, line in enumerate(job[script]):
                if re.search('choco install',line) and not re.search('\s-y',line):
                    job[script][linenumber] += " -y"

    # convert to string
    for script in ["install","script","before_install","before_script","after_success"]:

        if isinstance(job[script], list): 
            job["job" + script] = inspect.cleandoc("""
{}
""".format("\n".join(job[script])))
        else:
            job["job" + script] = job[script]
        job["job" + script]=job["job" + script].replace('travis_retry ', '')
        job["job" + script]= re.sub(r'travis_wait\s+[0-9]+','', job["job" + script])

# calculate hashes
for i, job in enumerate(travisyml["matrix"]["include"]):
    if job.get("jobinstall"):
        hash_object = hashlib.sha1(repr(job.get("jobinstall")).encode('utf-8'))
        job["jobinstalluuid"] = hash_object.hexdigest()[0:10]
        installdictionary[job["jobinstalluuid"]] += 1
    else:
        job["jobinstalluuid"] = "empty"

    if job.get("jobscript"):
        hash_object = hashlib.sha1(repr(job.get("jobscript")).encode('utf-8'))
        job["jobscriptuuid"] = hash_object.hexdigest()[0:10]
        scriptdictionary[job["jobscriptuuid"]] += 1
    else:
        job["jobscriptuuid"] = "empty"

try:
    boostinstalluuid=max(installdictionary, key=installdictionary.get)
except:
    boostinstalluuid=""
try:
    boostscriptuuid=max(scriptdictionary, key=scriptdictionary.get)
except:
    boostscriptuuid=""

substitution_ci_travis_install="""
if [ "$DRONE_STAGE_OS" = "darwin" ]; then
    unset -f cd
fi

export SELF=`basename $DRONE_REPO`
export BOOST_CI_TARGET_BRANCH="$DRONE_COMMIT_BRANCH"
export BOOST_CI_SRC_FOLDER=$(pwd)

. ./ci/common_install.sh"""

substitution_coverity="""if  [ -n "${COVERITY_SCAN_NOTIFICATION_EMAIL}" -a \( "$DRONE_BRANCH" = "develop" -o "$DRONE_BRANCH" = "master" \) -a "$DRONE_BUILD_EVENT" = "push" ] ; then"""
source_coverity="(env(COVERITY_SCAN_NOTIFICATION_EMAIL) IS present) AND (branch IN (develop, master)) AND (type IN (cron, push))"

# Processing main

for i, job in enumerate(travisyml["matrix"]["include"]):

    # Initialization
    job["joblcov"] = False
    job["jobos"] = "linux"
    job["jobfunction"] = "linux_cxx"

    if job.get("os") == "windows" or job.get("os") == None and travisyml.get("os") == "windows":
        job["jobos"] = "windows"
        job["jobfunction"] = "windows_cxx"
    elif job.get("os") == "osx" or job.get("os") == None and travisyml.get("os") == "osx":
        job["jobos"] = "osx"
        job["jobfunction"] = "osx_cxx"
    elif job.get("os") == "freebsd" or job.get("os") == None and travisyml.get("os") == "freebsd":
        job["jobos"] = "freebsd"
        job["jobfunction"] = "freebsd_cxx"

    # Numerical job number:
    job["jobnumber"] = i

    # Hash UUID:
    hash_object = hashlib.sha1(str(i).encode('utf-8'))
    job["jobuuid"] = hash_object.hexdigest()[0:10]

    # Define Environment Variables

    job["jobenv"]={}
    if job.get("env") and isinstance(job.get("env"), list):
        for item in job.get("env"):
            if isinstance(item, str):
                # almost always
                result=re.match('(\S+?)=(.*)',item)
                job["jobenv"][result.group(1)]=result.group(2).strip('"')
            elif isinstance(item, dict):
                # rarely
                for xitem in item:
                    job["jobenv"][xitem]=item[xitem].strip('"')

    elif job.get("env"):
        # Not a list. A string
        regex_doublequotes=r'(\w+)="([^"]+)"'
        regex_singlequotes=r"(\w+)='([^']+)'"
        regex_noquotes=r'(\w+)=([^\'"\s]+)'
        tempvalue = job.get("env").replace("\n"," ")

        locationofsinglequotes = tempvalue.find("'")
        locationofdoublequotes = tempvalue.find('"')

        if locationofdoublequotes > locationofsinglequotes:
            result = dict(re.findall(regex_singlequotes, tempvalue))
            tempvalue = re.sub(regex_singlequotes,'', tempvalue)
            result.update(dict(re.findall(regex_doublequotes, tempvalue)))
            tempvalue = re.sub(regex_doublequotes,'',tempvalue)
        else:
            result = dict(re.findall(regex_doublequotes, tempvalue))
            tempvalue = re.sub(regex_doublequotes,'', tempvalue)
            result.update(dict(re.findall(regex_singlequotes, tempvalue)))
            tempvalue = re.sub(regex_singlequotes,'',tempvalue)

        result.update(dict(re.findall(regex_noquotes, tempvalue)))

        job["jobenv"]=result

    elif travisyml.get("env") and isinstance(travisyml.get("env"), list):
        for item in travisyml.get("env"):
            if isinstance(item, str):
                # almost always
                result=re.match('(\S+?)=(.*)',item)
                job["jobenv"][result.group(1)]=result.group(2).strip('"')
            elif isinstance(item, dict):
                # rarely
                for xitem in item:
                    job["jobenv"][xitem]=item[xitem].strip('"')

    # Supplement Environment Variables
    if job["jobos"] != "linux":
        job["jobenv"]["DRONE_JOB_OS_NAME"]=job["jobos"]

    # Define Job CXX:
    # Order is important here. The last one takes precedence.
    job["jobcxx"] = "g++"
    jobenv=job["jobenv"]

    if job["jobos"] == "linux" or job["jobos"] == "osx":

        if job.get("compiler"):
            item = job.get("compiler")
            job["jobcxx"]=job.get("compiler")
            regex = '^gcc$'
            if item:
                result=re.match(regex,item)
                if result:
                    job["jobcxx"]="g++"
            regex = '^clang$'
            if item:
                result=re.match(regex,item)
                if result:
                    job["jobcxx"]="clang++"

        item = jobenv.get("TOOLSET")
        regex = '^gcc$'
        if item:
            result=re.match(regex,item)
            if result:
                job["jobcxx"]="g++"

        item = jobenv.get("TOOLSET")
        regex = '^clang$'
        if item:
            result=re.match(regex,item)
            if result:
                job["jobcxx"]="clang++"

        item = jobenv.get("B2_TOOLSET")
        regex = '^clang-(.*)$'
        if item:
            result=re.match(regex,item)
            if result :
                job["jobcxx"]="clang++-" + result.group(1)

        item = jobenv.get("B2_TOOLSET")
        regex = '^gcc-(.*)$'
        if item:
            result=re.match(regex,item)
            if result:
                job["jobcxx"]="g++-" + result.group(1)

        item = jobenv.get("B2_TOOLSET")
        regex = '^msvc-(.*)$'
        if item:
            result=re.match(regex,item)
            if result:
                job["jobcxx"]="msvc-" + result.group(1)


        item = jobenv.get("COMPILER")
        regex = '^(.*)$'
        if item:
            result=re.match(regex,item)
            if result:
                job["jobcxx"]=result.group(1)

        item = jobenv.get("CXX")
        regex = '^(.*)$'
        if item:
            result=re.match(regex,item)
            if result:
                job["jobcxx"]=result.group(1)

        # Exceptions. clang-3.x is often not able to compile boost.
        item = job["jobcxx"]
        regex = '^clang\+\+-(3.[01234567])$'
        if item:
            result=re.match(regex,item)
            if result:
                job["jobcxx"]="clang++"

        # Exceptions. gcc-4.x is often not able to compile boost.
        item = job["jobcxx"]
        regex = '^g\+\+-(4\.[123456])$'
        if item:
            result=re.match(regex,item)
            if result:
                job["jobcxx"]="g++"

    elif job["jobos"] == "windows":
        #Default
        job["jobcxx"]="g++"

        item = jobenv.get("CXX")
        regex = '^(.*)$'
        if item:
            result=re.match(regex,item)
            if result:
                job["jobcxx"]=result.group(1)

    # Special environment variables

    # asan requires this priv:
    if jobenv.get("COMMENT") and jobenv.get("COMMENT") == "asan":
        jobenv["DRONE_EXTRA_PRIVILEGED"] = "True"

    # check for the priv, in general:
    item = jobenv.get("DRONE_EXTRA_PRIVILEGED")
    if item:
         job["jobprivileged"]=item

    # Define Job Name:
    job["jobname"] = ""

    if job.get("name"):
        job["jobname"] = job.get("name")
    elif job.get("env") and isinstance(job.get("env"), list):
        tempname1=[]
        tempname2=[]
        tempname1=list(flatten(job['env']))
        for x in tempname1:
            if isinstance(x, str):
                regex = 'flags'
                result=re.search(regex,x,re.IGNORECASE)
                if not result:
                    tempname2.append(x)
        if tempname2:
            job["jobname"] = " ".join(tempname2[0:3])[0:45] + " Job " + str(i)
    elif job.get("env"):
        regex = 'flags'
        result=re.search(regex,job.get("env"))
        if not result:
            job["jobname"] += job['env'][0:45].replace("\n"," ") + " Job " + str(i)

    if job["jobname"] == "":
        job["jobname"] = "Job " + str(i)

    job["jobname"] = job["jobname"].replace('"', '')

    # Define Job Packages:
    templist=""
    job["jobpackages"] = ""
    if job.get('addons', {}).get('apt', {}).get('packages'):
        templist = list(flatten(job['addons']['apt']['packages']))
    elif travisyml.get('addons', {}).get('apt', {}).get('packages'):
        templist = list(flatten(travisyml['addons']['apt']['packages']))
  
    if templist:
        # Replace lcov package with newer lcov
        if 'lcov' in templist:
            job["joblcov"]=True
        templist = [s for s in templist if s != 'lcov']
        job["jobpackages"] = " ".join(templist)
        templist=""

    # Defining Job Sources, first step
    job["jobsources"] = ""
    if not job.get('addons', {}).get('apt', {}).get('sources') and travisyml.get('addons', {}).get('apt', {}).get('sources'):
        if not job.get('addons'):
            job['addons']={}
        if not job['addons'].get('apt'):
            job['addons']['apt']={}
        job['addons']['apt']['sources'] = travisyml['addons']['apt']['sources']

    # Define job dist, which will only be used "internally" for this script
    if job.get('dist'):
        job["jobdist"]=job.get('dist')
    elif travisyml.get("dist"):
        job["jobdist"]=travisyml.get("dist")
    else:
        job["jobdist"]="xenial"

    # Define Sources:
    # Example llvm-toolchain-xenial-4.0
    if job.get('addons', {}).get('apt', {}).get('sources'):
        if isinstance(job.get('addons', {}).get('apt', {}).get('sources'),list):
            for source in job.get('addons', {}).get('apt', {}).get('sources'):
                if isinstance(source, str):
                    result=re.match('(^llvm-)(toolchain-)(\S+)',source)
                    if result:
                        job["jobllvm_os"]=result.group(3)
                    # if there is also a version string, it will match the next regex and update the values:
                    result=re.match('(^llvm-)(toolchain-)(\S+)-(\S+)',source)
                    if result:
                        job["jobllvm_os"]=result.group(3)
                        job["jobllvm_ver"]=result.group(4)
                    result1=re.search('llvm',source)
                    result2=re.search('ubuntu-toolchain-r',source)
                    if not result1 and not result2:
                        job["jobsources"] += " " + source
                elif isinstance(source, dict):
                    for key,value in source.items():
                        result=re.match('.*(llvm-)(toolchain-)(\S+).*',value)
                        if result:
                            job["jobllvm_os"]=result.group(3)
                        # if there is also a version string, it will match the next regex and update the values:
                        result=re.match('.*(llvm-)(toolchain-)(\S+)-(\S+).*',value)
                        if result:
                            job["jobllvm_os"]=result.group(3)
                            job["jobllvm_ver"]=result.group(4)

        elif isinstance(job.get('addons', {}).get('apt', {}).get('sources'),str):
            source=job.get('addons', {}).get('apt', {}).get('sources')
            result=re.match('(^llvm-)(toolchain-)(\S+)',source)
            if result:
                job["jobllvm_os"]=result.group(3)
            # if there is also a version string, it will match the next regex and update the values:
            result=re.match('(^llvm-)(toolchain-)(\S+)-(\S+)',source)
            if result:
                job["jobllvm_os"]=result.group(3)
                job["jobllvm_ver"]=result.group(4)

    # specific fix, trusty->xenial:
    if job.get("jobllvm_os") == "trusty" and job.get("jobdist") == "xenial":
        job["jobllvm_os"] = "xenial" 

    # Define Image
    # example: image="ubuntu:14.04"
    # imagedict={"precise": "ubuntu:12.04", "trusty": "ubuntu:14.04", "xenial": "ubuntu:16.04", "bionic": "ubuntu:18.04", "focal": "ubuntu:20.04"}

    if job["jobos"] == "linux":
        job["jobimagedefault"] = "linuxglobalimage"
    elif job["jobos"] == "windows":
        job["jobimagedefault"] = "windowsglobalimage"

    imagedict={"precise": "cppalliance/droneubuntu1204:1", "trusty": "cppalliance/droneubuntu1404:1", "xenial": "cppalliance/droneubuntu1604:1", "bionic": "cppalliance/droneubuntu1804:1", "focal": "cppalliance/droneubuntu2004:1"}
    if job.get('dist'):
        job["jobimage"]=imagedict[job.get('dist')]

    if job["jobcxx"] == "msvc-14.1":
        job["jobimage"]="cppalliance/dronevs2017"
    if job["jobcxx"] == "msvc-14.2":
        job["jobimage"]="cppalliance/dronevs2019"

    # Main image
    if travisyml.get("dist"):
        travisyml["globalimage"]=imagedict[travisyml.get('dist')]
    else:
        # travisyml["globalimage"] = "ubuntu:16.04"
        travisyml["globalimage"] = "cppalliance/droneubuntu1604:1"

    # Define build type

    buildtypes=[]
    if job.get("jobinstalluuid") == boostinstalluuid and job.get("jobscriptuuid") == boostscriptuuid:
        job["jobbuildtype"]="boost"
    else:
        job["jobbuildtype"]=job.get("jobinstalluuid") + "-" + job.get("jobscriptuuid")
        buildtypes.append(job["jobbuildtype"])

    # point fixes to the install scripts
    # replace ci/travis/install.sh
    for script in ["jobinstall","jobscript","jobbefore_install","jobbefore_script","jobafter_success"]:
        if job.get(script):
            job[script] = re.sub(r'source ci/travis/install.sh',substitution_ci_travis_install,job.get(script))
            job[script] = re.sub(r'\. ci/travis/install.sh',substitution_ci_travis_install,job.get(script))
            job[script] = re.sub(r'mv \$TRAVIS_BUILD_DIR','cp -rp $TRAVIS_BUILD_DIR',job.get(script))
            job[script] = re.sub(r'mv "\$\{TRAVIS_BUILD_DIR\}"','cp -rp ${TRAVIS_BUILD_DIR}',job.get(script))
            job[script] = re.sub(r'BOOST_LIBS_FOLDER=\$\(basename \$TRAVIS_BUILD_DIR\)','BOOST_LIBS_FOLDER=$(basename $DRONE_REPO_NAME)',job.get(script))
            job[script] = re.sub(r'brew install','true brew install',job.get(script))
            job[script] = re.sub(r'brew upgrade','true brew upgrade',job.get(script))
            job[script] = re.sub(r'brew update','true brew update',job.get(script))
            job[script] = re.sub(r'brew outdated','true brew outdated',job.get(script))
            job[script] = re.sub(r'pip uninstall numpy','true pip uninstall numpy',job.get(script))
            job[script] = re.sub(r'which \$CC','true which $CC',job.get(script))
            job[script] = re.sub(r'\$CC --version','true $CC --version',job.get(script))
            job[script] = re.sub(r'\$\{CC\} --version','true ${CC} --version',job.get(script))
            job[script] = re.sub(r'export SELF=`basename \$TRAVIS_BUILD_DIR`','export SELF=`basename $DRONE_REPO`',job.get(script))

            if job["jobos"] != "linux":
                job[script] = re.sub(r'gem install coveralls-lcov','true gem install coveralls-lcov',job.get(script))

    # gcov-6 requires gcc-6
    for script in ["jobinstall","jobscript","jobbefore_install","jobbefore_script","jobafter_success"]:
        if job.get(script) and re.search(r'gcov-6',job.get(script)) and job.get("jobpackages") and not re.search(r'gcc-6',job["jobpackages"]):
                job["jobpackages"] += " gcc-6"
                break

    # gcov-7 requires gcc-7
    for script in ["jobinstall","jobscript","jobbefore_install","jobbefore_script","jobafter_success"]:
        if job.get(script) and re.search(r'gcov-7',job.get(script)) and job.get("jobpackages") and not re.search(r'gcc-7',job["jobpackages"]):
                job["jobpackages"] += " gcc-7"
                break

    # gcov-8 requires gcc-8
    for script in ["jobinstall","jobscript","jobbefore_install","jobbefore_script","jobafter_success"]:
        if job.get(script) and re.search(r'gcov-8',job.get(script)) and job.get("jobpackages") and not re.search(r'gcc-8',job["jobpackages"]):
                job["jobpackages"] += " gcc-8"
                break

    # set TRAVIS_COMPILER if required
    for script in ["jobinstall","jobscript","jobbefore_install","jobbefore_script","jobafter_success"]:
        if job.get(script) and re.search(r'TRAVIS_COMPILER',job.get(script)) and job.get("compiler"):
                job["jobenv"]["TRAVIS_COMPILER"] = job["compiler"]
                break

    if job.get('if'):
        if source_coverity in job.get('if'):
            job["jobscript"] = substitution_coverity + "\n" + job["jobscript"]
            job["jobscript"] += "\nfi"

    # Add uuid as an environment variable
    job["jobenv"]["DRONE_JOB_UUID"] = job["jobuuid"]

    # Switch to the right version of xcode
    if job.get("osx_image"):
        result1=re.search('^xcode([0-9]+)$', job.get("osx_image"))
        result2=re.search('^xcode([0-9]+\.[0-9]+)$', job.get("osx_image"))
        result3=re.search('^xcode([0-9]+\.[0-9]+\.[0-9]+)$', job.get("osx_image"))
        if result1:
            job["jobxcode_version"]=result1.group(1)
        elif result2:
            job["jobxcode_version"]=result2.group(1)
        elif result3:
            job["jobxcode_version"]=result3.group(1)

        if cwd == "yap":
            del job["jobxcode_version"]

    # Move interpolated environment variables to before-install
    for item in dict(reversed(list(job["jobenv"].items()))):    
        if re.search('\$',job["jobenv"][item]):
            job["jobbefore_install"] = "export " + item + "=\"" + job["jobenv"][item] + "\"\n" + job["jobbefore_install"]
            job["jobenv"].pop(item, None)

    # Replace lcov package with newer version
    if job["joblcov"]:
        job["jobbefore_install"] +="\nwget http://downloads.sourceforge.net/ltp/lcov-1.14.tar.gz\ntar -xvf lcov-1.14.tar.gz\ncd lcov-1.14\nmake install && cd .."

# Main processing loop completed ###############################################################

# Process global environment variables
travisyml["globalenv"]={}
if travisyml.get("env") and isinstance(travisyml.get("env"), dict):
    if travisyml.get("env",{}).get("global") and isinstance(travisyml.get("env",{}).get("global"), list):
        for item in travisyml["env"]["global"]:
            if isinstance(item, str):
                # almost always
                result=re.match('(\S+?)=(.*)',item)
                travisyml["globalenv"][result.group(1)]=result.group(2).strip('"')
            elif isinstance(item, dict):
                # rarely
                for xitem in item:
                    travisyml["globalenv"][xitem]=item[xitem].strip('"')
    elif travisyml.get("env",{}).get("global"):
        result=re.match('(\S+?)=(.*)',travisyml["env"]["global"])
        travisyml["globalenv"][result.group(1)]=result.group(2).strip('"')

# Move interpolated global environment variables to before-install
for item in dict(reversed(list(travisyml["globalenv"].items()))):
    if re.search('\$',travisyml["globalenv"][item]):
        for i, job in enumerate(travisyml["matrix"]["include"]):
            job["jobbefore_install"] = "export " + item + "=\"" + travisyml["globalenv"][item] + "\"\n" + job["jobbefore_install"]
        travisyml["globalenv"].pop(item, None)

# Collect scripts together for templates
travisyml["jobbefore_install_collection"]={}
travisyml["jobbefore_script_collection"]={}
travisyml["jobafter_success_collection"]={}

for i, job in enumerate(travisyml["matrix"]["include"]):
    uuid = job["jobuuid"]

    jobbefore_install=job.get("jobbefore_install")
    if jobbefore_install:
        if travisyml["jobbefore_install_collection"].get(jobbefore_install):
            travisyml["jobbefore_install_collection"][jobbefore_install].append(uuid)
        else:
            travisyml["jobbefore_install_collection"][jobbefore_install] = [uuid]

    jobbefore_install=job.get("jobbefore_script")
    if jobbefore_install:
        if travisyml["jobbefore_script_collection"].get(jobbefore_install):
            travisyml["jobbefore_script_collection"][jobbefore_install].append(uuid)
        else:
            travisyml["jobbefore_script_collection"][jobbefore_install] = [uuid]

    jobafter_success=job.get("jobafter_success")
    if jobafter_success:
        if travisyml["jobafter_success_collection"].get(jobafter_success):
            travisyml["jobafter_success_collection"][jobafter_success].append(uuid)
        else:
            travisyml["jobafter_success_collection"][jobafter_success] = [uuid]


# Output templates ####################################################

filename = '.drone.star'
outputfile = open(filename, 'w')
template = env.get_template('drone.star')
print(template.render(travisyml=travisyml),file=outputfile)
outputfile.close()
os.chmod(filename, 0o644)

os.makedirs(".drone", exist_ok=True)

# Moving these files to boost-ci
#
# filename = '.drone/linux-cxx-install.sh'
# outputfile = open(filename, 'w')
# template = env.get_template('linux-cxx-install.sh')
# print(template.render(travisyml=travisyml),file=outputfile)
# outputfile.close()
# os.chmod(filename, 0o755)
# 
# filename = '.drone/windows-msvc-install.sh'
# outputfile = open(filename, 'w')
# template = env.get_template('windows-msvc-install.sh')
# print(template.render(travisyml=travisyml),file=outputfile)
# outputfile.close()
# os.chmod(filename, 0o755)
# 
# filename = '.drone/osx-cxx-install.sh'
# outputfile = open(filename, 'w')
# template = env.get_template('osx-cxx-install.sh')
# print(template.render(travisyml=travisyml),file=outputfile)
# outputfile.close()
# os.chmod(filename, 0o755)

for i, job in enumerate(travisyml["matrix"]["include"]):
    buildtype=job.get('jobbuildtype')
    filename = '.drone/' + buildtype + '.sh'
    outputfile = open(filename, 'w')
    template = env.get_template('template-script.sh')
    print(template.render(install=job['jobinstall'],script=job['jobscript']),file=outputfile)
    outputfile.close()
    os.chmod(filename, 0o755)

    filename = '.drone/before-install.sh'
    outputfile = open(filename, 'w')
    template = env.get_template('before-install.sh')
    print(template.render(travisyml=travisyml),file=outputfile)
    outputfile.close()
    os.chmod(filename, 0o755)

    filename = '.drone/before-script.sh'
    outputfile = open(filename, 'w')
    template = env.get_template('before-script.sh')
    print(template.render(travisyml=travisyml),file=outputfile)
    outputfile.close()
    os.chmod(filename, 0o755)

    filename = '.drone/after-success.sh'
    outputfile = open(filename, 'w')
    template = env.get_template('after-success.sh')
    print(template.render(travisyml=travisyml),file=outputfile)
    outputfile.close()
    os.chmod(filename, 0o755)

print("Conversion complete. Check .drone.star and .drone/")
