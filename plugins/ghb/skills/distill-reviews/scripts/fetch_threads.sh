#!/bin/bash
# usage: fetch_threads.sh <owner/repo> <since YYYY-MM-DD> <out_dir>
# Writes one JSON file per PR merged since <since>: files, commits, review bodies, review threads.
# Reviewer identities are reduced to copilot / bot / pr-author / human-reviewer so no
# usernames reach the agents or the PR this pipeline opens.
set -euo pipefail
REPO=$1 SINCE=$2 OUT=$3
OWNER=${REPO%/*} NAME=${REPO#*/}
mkdir -p "$OUT"
nums=$(gh pr list --repo "$REPO" --state merged --search "merged:>=$SINCE -label:distill-reviews" \
  --limit 300 --json number --jq '.[].number')
Q='query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){pullRequest(number:$n){number title mergedAt author{login}
 files(first:100){nodes{path}}
 commits(first:100){nodes{commit{oid messageHeadline committedDate}}}
 reviews(first:50){nodes{author{login __typename} state body}}
 reviewThreads(first:100){nodes{isResolved isOutdated path line
  comments(first:30){nodes{author{login __typename} body createdAt diffHunk}}}}}}}'
for n in $nums; do
  gh api graphql -f query="$Q" -F o="$OWNER" -F r="$NAME" -F n="$n" --jq '
   .data.repository.pullRequest as $p | ($p.author.login) as $a |
   def who: if .author==null then "unknown" elif (.author.login|test("copilot";"i")) then "copilot"
            elif .author.__typename=="Bot" then "bot" elif .author.login==$a then "pr-author" else "human-reviewer" end;
   {number:$p.number, title:$p.title, mergedAt:$p.mergedAt,
    files:[$p.files.nodes[].path],
    commits:[$p.commits.nodes[].commit|{sha:.oid[0:10],msg:.messageHeadline,at:.committedDate}],
    reviews:[$p.reviews.nodes[]|select((.body|length)>0)|{by:who,state,body:.body[0:1500]}],
    threads:[$p.reviewThreads.nodes[]|{isResolved,isOutdated,path,line,
      comments:[.comments.nodes|to_entries[]|.value as $c|{by:($c|who),at:$c.createdAt,body:$c.body[0:2000]}
                + (if .key==0 then {diffHunk:($c.diffHunk|.[-1500:])} else {} end)]}]}' > "$OUT/pr-$n.json"
done
ls "$OUT" | wc -l | xargs echo "PRs fetched:"
