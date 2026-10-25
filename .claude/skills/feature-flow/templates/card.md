---
id: <NN>
title: <verb + what, e.g. "Show a page's backlinks under its text">
wave: <0, 1, 2…>
depends_on: [<ids>]
files:
  - <path this card creates or edits, exclusive in its wave>
status: todo  # todo | doing | done | blocked
branch:       # filled on integration
---

## Goal

<One or two sentences: which part of the spec this card delivers.>

## Context

- Exemplar to copy: `<file>` (<what to copy from it>)
- Already exists and must be used: `<class/method>`
- Wave 0 contracts this card consumes: `<model/config>`

## What to do

- <concrete step, per concept>

## Acceptance criteria

- <verifiable condition that fails today and passes with this card>

## Tests

- `<tests/area/test_x.py>::<TestClass>::<test_name>`: <the behavior it locks>
- or: None: <why, e.g. only wiring, covered by card NN's test>

## Do not touch

- <behavior or file that must stay as it is>
