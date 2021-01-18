# Use, modification, and distribution are
# subject to the Boost Software License, Version 1.0. (See accompanying
# file LICENSE.txt)
#
# Copyright Rene Rivera 2020.

# For Drone CI we use the Starlark scripting language to reduce duplication.
# As the yaml syntax for Drone CI is rather limited.
#
#
globalenv={{ travisyml['globalenv'] }}
linuxglobalimage="{{ travisyml['globalimage'] }}"
windowsglobalimage="cppalliance/dronevs2019"

def main(ctx):
  return [
  {% set jobs = travisyml["matrix"]["include"] -%}
  {% for job in jobs -%}
  {% if job["jobfunction"] != "freebsd_cxx" -%}
  {{ job["jobfunction"] }}("{{ job['jobname'] }}", "{{ job['jobcxx'] }}", packages="{{ job['jobpackages'] }}"{% if job['jobsources'] is defined and job['jobsources']|length  %}, sources="{{ job['jobsources'] }}"{% endif -%}{% if job['jobllvm_os'] is defined %}, llvm_os="{{ job['jobllvm_os'] }}"{% endif -%}{% if job['jobllvm_ver'] is defined %}, llvm_ver="{{ job['jobllvm_ver'] }}"{% endif %}{% if job['jobbuildtype'] is defined %}, buildtype="{{ job['jobbuildtype'] }}"{% endif %}{% if job['jobimage'] is defined %}, image="{{ job['jobimage'] }}"{% elif job['jobimagedefault'] is defined %}, image={{ job['jobimagedefault'] }}{% endif %}{% if job['jobosx_version'] is defined %}, osx_version="{{ job['jobosx_version'] }}"{% endif %}{% if job['jobxcode_version'] is defined %}, xcode_version="{{ job['jobxcode_version'] }}"{% endif %}{% if job['jobenv'] is defined and job['jobenv']|length %}, environment={{ job['jobenv'] }}{% endif %}, globalenv=globalenv{% if job['jobprivileged'] is defined %}, privileged={{ job['jobprivileged'] }}{% endif %}),
  {% endif %}{% endfor -%}
    ]

# from https://github.com/boostorg/boost-ci
load("@boost_ci//ci/drone/:functions.star", "linux_cxx","windows_cxx","osx_cxx","freebsd_cxx")
