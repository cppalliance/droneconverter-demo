#!/bin/bash

{% if travisyml["jobbefore_install_collection"] is defined -%}
{% for task in travisyml["jobbefore_install_collection"] -%}
if {% for job in travisyml["jobbefore_install_collection"][task] -%}
{% if loop.index == 1 -%} [ "$DRONE_JOB_UUID" = "{{ job }}" ] {% else -%} || [ "$DRONE_JOB_UUID" = "{{ job }}" ] {% endif -%} {% endfor -%} ; then {%- filter indent(width=4) %}
{{ task }}
{% endfilter -%}
fi
{% endfor -%}
{% endif -%}
