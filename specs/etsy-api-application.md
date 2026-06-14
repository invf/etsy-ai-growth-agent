# Etsy API re-application — draft

Submit in English via the Etsy Developer portal. Written first-person as the
shop owner, single-shop use case, human-in-the-loop. No SaaS / third-party
framing anywhere.

---

## App name

AI Listing Optimizer

## What are you building? / Describe your application

I run three small shops on Etsy myself, and I'm building a private tool to help
me keep my own listings in better shape. My shops are quite different from each
other — one sells hand-embroidered paintings, one sells knitted clothes for
small dogs, and one sells digital downloads — so I spend a lot of time rewriting
titles, picking tags and tidying up descriptions, and I'm honestly not getting
the traffic I'd like.

The tool reads the listings in my own shops and helps me draft better titles,
tag sets and descriptions. Nothing is changed on Etsy automatically. Every
suggestion shows up as a draft that I read, edit and approve myself before
anything is sent back, and I only ever apply changes to listings in my own
shops. It's just for me — I'm the only person using it, and it isn't a service
I'm offering to anyone else.

## How will you use Etsy's API?

- Read my own shops and listings (titles, tags, descriptions, basic stats) so I
  can see what I have and where to improve.
- When I've reviewed and approved a change myself, write that single update back
  to the specific listing it belongs to.

That's the whole flow: read my listings, I review the drafts, I approve, it
updates that one listing. No bulk edits, no scheduled or automatic publishing,
and nothing acting on behalf of any other person or shop.

## Scopes requested

- `listings_r` — read my listings.
- `listings_w` — apply the individual changes I've personally approved.

(If read-only is enough to get started, I'm happy to begin with `listings_r`
only and add write access later.)

## Request volume

Very low. It only ever touches my three shops, runs when I'm actually working on
a listing, and stays well under the rate limits — I've capped my own client at
5 requests per second. I'm not polling in the background or pulling data I don't
need.

## Commercial use

This is for managing my own Etsy shops. It isn't sold, resold, or made available
to other sellers.

---

# Short version (for fields with a character limit)

## Description (~470 chars)

I run three of my own Etsy shops — hand-embroidered paintings, knitted clothes
for small dogs, and digital downloads — and I'm building a private tool just for
me to improve my own listings. It reads my listings and drafts better titles,
tags and descriptions. Nothing changes automatically: I review, edit and approve
every suggestion myself before it's applied, and only to my own listings. I'm
the only user; it isn't sold or offered to other sellers.

## How I'll use the API (~290 chars)

Read my own listings (titles, tags, descriptions, stats), then write back only
the individual changes I've personally approved — one listing at a time. No bulk
edits, no automatic publishing, nothing on behalf of others. Scopes: listings_r
and listings_w. Low volume, only my three shops, capped at 5 req/s.

## One-liner (if there's a tiny summary field, ~120 chars)

A private tool I use to review and improve the listings in my own three Etsy
shops, with every change approved by me.
