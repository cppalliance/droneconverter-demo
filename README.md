
## Drone Converter Demo  

### A python script to convert .travis.yml to .drone.star, for Boost Libraries.

This repository is a code example to accompany a blog post at https://cppalliance.org. If you are a boost author implementing Drone, refer to https://github.com/CPPAlliance/drone-ci for support and documentation.  

Instructions:

Install PyYAML:
```
pip3 install --ignore-installed PyYAML
```

Place droneconverter in the standard Python package path, or modify PYTHONPATH. For example:
```
PYTHONPATH=/opt/github/CPPAlliance:$PYTHONPATH
```

Copy bin/droneconverter to your PATH:
```
cp /opt/github/droneconverter/bin/droneconverter /usr/local/bin
```

Change directories to the target git repository. For example:
```
cd /opt/github/boostorg/beast
```

Run the command:
```
droneconverter
```

.drone.star and the .drone directory will be created. Check in the changes to github.  

Next, you may link the repository to a Drone CI server by logging into drone.cpp.al (a build server available for boostorg) or cloud.drone.io, syncing all repos, and then activating particular repos.  In the repository's Settings, change the configuration from .drone.yml to .drone.star. Save.

Review [known-issues](docs/known-issues.md).
