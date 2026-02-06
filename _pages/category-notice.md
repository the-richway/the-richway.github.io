---
title: "공지사항"
layout: archive
permalink: /categories/notice/
author_profile: false
sidebar:
  nav: "sidebar"
---

{% assign entries_layout = page.entries_layout | default: 'list' %}
{% assign posts = site.categories['공지사항'] %}
{% for post in posts %}
  {% include archive-single.html type=entries_layout %}
{% endfor %}