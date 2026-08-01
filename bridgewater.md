

Introduction: 50 years of written-down investment logic as an AI advantage
0:06
>> Hello, everyone.
0:08
My name is Brendan McManus, the team lead of the applied AI team at Bridgewater Associates,
0:12
a systematic macro hedge fund.
0:14
I've been at Bridgewater for almost a decade now, where I started as a software engineer,
0:19
then became a systematic investor and researcher, and for the past few years I've been focused
0:24
heavily on bridging the gap between investing and technology.
0:27
I'm here today with my colleagues Michael Ran and Santi
0:30
Weight, our investor lead and technical lead
0:32
of this project respectively, to talk to you about a great tool
0:36
that we built internally called PAT, the Pocket Analyst Tool.
0:39
By the end of this talk, all of you
0:42
should have seen how we built an AI analyst that's
0:45
capable of performing hours of expert research work
0:48
in minutes — that's been internally deployed
0:50
to hundreds of investors and that learns
0:53
from every single interaction.
0:55
On top of that, we'll also show you exactly how we architected such a thing.
1:00
So before we show you what we built,
1:02
I wanted to go through some quick framing on Bridgewater's approach to AI.
1:07
Bridgewater has been spending decades — 50 years —
1:10
thinking about how to encode markets and economies into compounding systems.
1:15
And all of this really started with what you're seeing on the screen:
1:18
our 1980 bond system, written down on a yellow legal pad.
1:22
The idea here was quite simple.
1:24
Every time you wanted to make a trade,
1:26
write down exactly the rules for why you think that trade makes sense.
1:30
Write down the exact causal logic.
1:32
Because once you do this,
1:33
another investor can take a look at what you've written,
1:36
help you figure out where you went wrong,
1:38
and help you improve upon this process.
1:41
Every time you learn something new, you scratch out a rule,
1:43
you write down a new one,
1:45
and this creates a pretty incredible learning process
1:47
that has been the foundation of everything that we've done at Bridgewater
1:50
for the past 50 years.
Bridgewater's approach to AI: as investors and as practitioners
1:52
Over the decades, we've compounded upon this process
1:54
significantly, taking every lesson, every methodology, every rule that we've
1:59
developed about the trades we make — how and why — and codifying them into
2:04
an expert system that's both machine-readable and human-readable.
2:07
And it's really now that we're sitting on a pretty tremendous trove of data.
2:12
And all of this data is really what sets us up well for the AI era.
2:16
We didn't have to go back and write down everything for agents.
2:19
It was already there for us to draw upon.
2:22
Before we get into the tool,
2:24
I wanted to talk about how we're approaching AI at Bridgewater
2:26
more generally.
2:27
We're doing this in two ways.
2:28
The first is as investors.
2:30
As investors, we need to deeply understand
2:32
every major dynamic that's shaping global markets
2:35
and economies.
2:36
Just as we had to understand COVID or the recent oil supply
2:39
shock, we've also had to understand AI.
2:42
What's the shape of the supply-demand mismatch?
2:45
What's driving the buildout?
2:47
And how do these things ultimately impact markets?
2:49
This understanding is table stakes for us as investors.
2:53
The second way we're approaching AI
2:54
is as practitioners — which is what we're mostly
2:57
going to be spending our time on here today.
2:59
As practitioners, we're applying AI
3:01
across all aspects of our research process,
3:03
with the ultimate goal of building out
3:05
an artificial investor that's capable of the full range
3:08
of activities that our human investors are performing
3:10
every single day.
The research circle and the artificial investor roadmap
3:11
So what do our human investors actually do?
3:14
Well, we think about it as a research circle.
3:16
Investors are constantly perceiving
3:18
what's happening in the outside world,
3:20
formulating questions about what is true
3:22
and what they might potentially be missing,
3:24
performing analytical investigations
3:26
to try to answer these questions,
3:29
synthesizing their findings,
3:30
and ultimately taking anything that they learned
3:32
and putting it back into the compounded understanding —
3:34
the expert systems that we've built out.
3:37
It's really this last step that's key.
3:39
Everything that we learn as a function of this process
3:41
gets put back into a shared memory
3:43
that humans are able to draw upon.
3:47
And so you might imagine that if you're
3:51
going to build out an artificial investor,
3:53
they need to be able to do all of the different steps
3:55
of this research process.
3:57
You can imagine having built out discrete sub-agents
4:01
focused on each portion of the research circle.
4:04
And that's exactly how we're approaching AI.
4:06
We're building out discrete sub-agents
4:08
for each of these different things
4:09
that human investors must do, drawing upon the same understanding
4:13
that we've built up over the last 50 years.
4:16
But today, we're only going to be talking about one of these
4:18
agents — the one focused on the
4:20
investigation portion of the research process: the kinds of
4:24
deep analytical work that take our human analysts days and
4:27
weeks to perform.
4:29
We called this tool PAT, the Pocket Analyst Tool.
PAT: what it is and what it's not
4:32
And just to set expectations: PAT is not about how we trade.
4:36
It's really about performing deep exploratory research,
4:39
enabling our investors to go after questions that they
4:41
never would have had the bandwidth to pursue before.
4:44
So what did we actually build?
4:46
We built PAT, the Pocket Analyst Tool.
4:49
And from day one, the spec was simple.
4:52
We had to enable PAT to do all of the things
4:54
that our human investors are doing
4:56
as they perform investigatory or analytical work.
5:00
And that really starts with data.
What PAT had to do: data, tools, diagnosable analyses, context, and learning
5:01
PAT had to be able to search across
5:03
and read all of the different data that we have internally —
5:05
from structured time series data,
5:07
for example, stock prices going back decades,
5:10
to unstructured data, for example,
5:12
broker-dealer research pieces that we subscribe to,
5:14
or internal memos that we produce.
5:16
PAT has to be able to search across and read all of it.
5:19
PAT also has to be able to use all of the different tools
5:21
that our human analysts have access to.
5:23
All of the proprietary tools that we've built out
5:25
for visualization, for diagnostics,
5:27
or for evaluating the quality of the indicator ideas
5:29
that we've built out.
5:31
In addition to this — and this is where things
5:33
might get a little bit more interesting
5:34
for a technical audience — many of the analyses
5:37
that PAT is running would take a human analyst
5:39
many hours to run.
5:41
And this means that the analyses are quite complex,
5:45
which means that PAT's analyses
5:46
have to be completely diagnosable —
5:48
not just for humans, but also for agents
5:51
running in the background, reading through the traces,
5:53
understanding and making sure
5:55
that every calculation is correct.
5:57
On top of this — and this is really where
5:59
building upon all of the things that we've written down
6:02
over the past 50 years starts to pay off —
6:03
PAT knows all of our context.
6:06
It has access to all of our investment processes,
6:09
our frameworks. It knows exactly how our analysts
6:11
are supposed to be doing work, because we've been writing it
6:13
down for the past 50 years.
6:15
And lastly, PAT has to learn.
6:17
It has to compound upon its own learning,
6:20
not just for one investor, but for every investor
6:22
at the firm.
How a 50-year-old hedge fund actually builds this
6:24
PAT is not a prototype today.
6:26
It was actually deployed internally several months ago.
6:28
And we now have hundreds of investors using it every single
6:30
day, which is leading to a pretty incredible flywheel
6:34
of improvement: as investors use
6:37
PAT for real research, we have agents continuously
6:40
running in the background, scanning through these interactions,
6:42
figuring out where PAT went wrong,
6:44
developing human-audited benchmarks, which then
6:47
results in changes to context, and also
6:49
to the harnesses that we built for PAT — which results in PAT
6:52
improving not just for one, but for everyone.
6:56
And lastly, before we get into what we built,
6:58
I wanted to leave you with one question
6:59
that I pretty commonly get, which is:
7:01
how does a 50-year-old hedge fund actually
7:03
build out something like what you're about to see?
7:06
Well, it really starts with being
7:08
willing to shake yourself up.
Multi-archetype teams: investors, technologists, and scientists side by side
7:09
The team that built out PAT was ultimately
7:11
an internal applied AI startup that
7:14
was incubated within the broader firm,
7:16
with the ability to move incredibly flexibly and quickly
7:19
while being able to draw upon the resources of the broader firm.
7:23
In addition to this, we've established multi-archetype
7:26
teams where we have investors, technologists,
7:28
and scientists sitting side by side,
7:31
building alongside each other.
7:34
And I think this is really a key thing
7:36
if you're going to build out a product like this.
7:39
Investors bring the context and the domain-specific expertise.
7:43
Technologists bring the architectural capability.
7:45
And scientists bring the rigor.
7:47
It's really these types of multi-archetype teams
7:49
that are necessary if you're going to build AI systems
7:52
for expert users.
7:53
And speaking of expert users, we have hundreds of them
7:56
internally using all of our AI tools —
7:59
not just PAT — generating signal
8:02
daily on how these things should be evolving
8:04
and improving over time.
8:06
And lastly, we have a pretty incredible compounding
8:08
ecosystem to plug into.
8:10
50 years of shared data, tooling, and methodologies,
8:13
all built out not just for our human analysts to plug into,
8:16
but also for agents on our journey
8:18
to build out a fully artificial investor that's
8:21
capable of everything that humans are able to do today.
8:24
And so with that, I'm going to pass things off
8:25
to Michael Ran, investor lead, to go through a demo of what
8:28
we built and take you through the product architecture.
Demo: PAT live — oil supply shocks and the Middle East conflict
8:32
All right.
8:32
Thank you, Brendan.
8:34
[APPLAUSE]
8:36
My name is Michael Ran.
8:37
I'm the investor lead working on the Pocket Analyst Tool,
8:39
and a little bit about myself:
8:41
I've been at Bridgewater for five years,
8:42
where I joined as a technologist
8:44
but have spent most of my time in an investor role.
8:46
And nowadays, the thing I'm mostly focused on
8:48
is how we can infuse AI into our investment process.
8:51
With that, I'd love to jump into a demo
8:53
of the Pocket Analyst Tool to highlight its capabilities
8:56
and show you how investors at Bridgewater are using it.
8:59
Behind me you can see the PAT landing page,
9:01
which has the prompt we'll be using for today's demo.
9:04
The gist of it: we're asking PAT
9:06
to look at how markets have responded
9:07
to the recent conflict in the Middle East
9:09
and to compare today's events to similar historical episodes.
9:12
Then lastly, we asked PAT to put together
9:14
some visualizations that highlight
9:16
how similar or dissimilar today is
9:18
relative to previous oil supply shocks.
9:21
This is a real question we've been working on at Bridgewater
9:23
over the past couple of months,
9:24
and PAT has been a tool leveraged by investors
9:26
to help expedite our research process.
9:29
But before we submit the prompt,
9:30
I'd like to spend a moment talking
9:31
about an interesting security problem
The per-user security problem: every investor gets their own PAT
9:33
we ran into when designing PAT's harness.
9:37
Our starting point was: for PAT to truly be helpful,
9:40
it needs to be able to access all of the information
9:42
that investors have access to when conducting research.
9:44
But the thing is, at Bridgewater,
9:46
different investors have access to different information.
9:49
So for example, you may have one investor
9:51
who has access to what our positions are across all markets
9:53
today, and it's important for that person's PAT
9:55
to also have this information.
9:57
But then you might have analysts who are not exposed to this,
9:59
and it's similarly critical that we do not accidentally
10:01
leak that secure IP to those analysts.
10:04
So unlike a harness like Claude Code,
10:05
where everyone is interfacing with the same system prompt
10:08
and the same tools, each person at Bridgewater
10:10
has a unique version of PAT tailored
10:12
to what they can and cannot see.
10:14
Practically speaking, this uniqueness
10:17
is just a function of what context
10:18
and what tools each person's PAT has.
10:20
So with that, we'll go ahead and submit the prompt.
Time series search with human-like inspection: 50% to 90% accuracy
10:24
The first thing that takes place in this analysis
10:26
is PAT searches the web and our vault of unstructured data
10:29
to better understand what's happening in the world today,
10:31
contextualized against history.
10:34
Web search itself is table stakes
10:36
when it comes to these modern chat applications.
10:38
But the real differentiator here
10:39
is the breadth of unstructured content
10:41
that we subscribe to that PAT is able to search over.
10:44
We have a database containing millions of documents
10:46
from all around the world that includes content
10:48
such as broker pieces, earnings transcripts,
10:51
internal emails, and more.
10:52
And this database is updating in near real time,
10:55
with thousands of new pieces coming in each day.
10:57
And this ties back to the point I was making on the previous
10:59
slide: for PAT to really provide leverage, it has to access everything that
11:03
its user has access to, such that it can try and emulate what its users actually do.
11:09
Once this context is gathered, the next thing PAT does is search our time
11:13
series database for the data required for the analysis.
The plan is the analysis: clarifying questions and high-quality research plans
11:16
This is a database that contains tens of millions of series that we've been modeling internally
11:20
for 50 years, and this database contains data from the outside world — like the price of oil —
11:25
and also internally derived concepts,
11:27
such as what we think inflation will be 12 months out.
11:30
The search agents use traditional
11:32
search techniques like RAG, re-ranking, et cetera,
11:35
but the thing we found to be a huge difference-maker
11:38
was layering on an element of human-like inspection.
11:40
What I mean by that is: when a human researcher
11:42
is looking for data, they don't just anchor
11:44
to what the name of the time series is.
11:46
They'll look at the frequency,
11:48
the currency of the series, and then most importantly,
11:50
whether the values in the series align with their priors.
11:53
So embedding this sort of reasoning into our search
11:55
agent is something that got us up from roughly
11:57
50% accuracy all the way to 90%.
12:01
Now, after PAT has context and data at hand,
12:05
it comes back to the user with clarifying questions
12:07
and potentially ideas for additional angles to explore.
12:10
During PAT's development, we came to the view
12:12
that the plan really is the analysis.
12:14
If we can create a high-quality, detailed plan,
12:17
we felt confident that we could consistently take this plan,
12:20
intelligently execute it, and produce our desired outputs.
12:23
Santi will be diving into this a bit more later.
12:25
So while agents asking clarifying questions
12:27
is pretty standard in chatbots nowadays,
12:29
the thing we really focused on
12:30
was the substance of those questions.
12:32
We devoted lots of time and energy
12:34
into developing the context and benchmarks
12:36
that helped shape this capability.
12:38
We taught PAT what makes a good research question
12:40
versus a bad one, so this back-and-forth helps humans —
12:42
who tend to under-invest in planning —
12:44
flesh out what we consider to be
12:45
a high-quality research plan.
Parallel code generation: 3-task and 20-task plans take the same time
12:49
Now, after the ambiguous points are all resolved,
12:51
PAT enters its planning phase.
12:53
During the planning phase, the things it's doing are: A,
12:56
coming up with all of the data frames
12:57
that will be produced in the analysis;
12:59
coming up with the schemas of all of those data frames;
13:02
and then most importantly,
13:03
coming up with how all those data frames connect.
13:05
This planning phase is relatively expensive
13:08
from a time perspective,
13:10
but it's a cost we pay deliberately
13:12
because of what it lets us do during execution.
13:15
So now we have the plan locked in,
13:17
and the first step of plan execution is generating the code.
13:21
Given we have such a detailed plan,
13:23
we're able to generate the code
13:25
for each data frame in our analysis
13:27
in parallel using sub-agents.
13:28
And this works because each sub-agent knows
13:30
what data frames it depends on,
13:32
knows the schemas of those data frames,
13:34
and also knows what the schema of the data frame
13:36
it's producing should be.
13:37
So this lets an analysis
13:40
with three data frames or a medium-sized one
13:42
with something like 30 data frames
13:43
take roughly the same amount of time
13:45
to generate code in both scenarios.
13:48
Once we finish generating the code,
13:49
we execute the Python functions
13:51
with an agent overseeing this execution
13:53
and stepping in if it sees things like runtime errors
13:56
or nonsensical values.
13:57
And before we proceed from execution,
13:59
I want to call out the fact that the time series outputs
14:02
from these analyses land in the same database
14:04
that we actually pulled our inputs from.
14:06
And I think this is important for a couple of reasons.
14:08
One: it shows that any output from a PAT analysis
14:11
is indistinguishable from any of the human-uploaded series
14:13
that we've been producing for many years.
14:15
And more importantly, any output from a PAT analysis
14:18
can serve as an input to a subsequent one.
14:20
So this creates an environment
14:22
where humans and agents can very easily compound
14:24
and leverage each other's work.
Self-correction: PAT checks its own work before returning results
14:27
Now, after execution completes,
14:30
just like you'd want your junior analyst
14:31
to double-check their work before coming back to you,
14:33
we want PAT to do the same.
14:34
So at this point in the analysis,
14:36
PAT will look at the data that's been computed
14:38
and the visualizations it's produced
14:40
and make sure that the numbers seem sensible
14:42
and the charts look clean.
14:43
If it sees something that looks a bit off,
14:45
PAT will take a step back, diagnose the issue,
14:48
refine the analysis, and make sure it's satisfied
14:51
with its result before coming back to the user.
14:54
And then the result itself is this interactive report
14:57
where the visualizations look just like
14:59
the ones investors at Bridgewater are producing.
15:01
PAT is using the same in-house charting library
15:04
and leveraging the same existing text deck
15:06
that we've been developing internally for decades.
15:08
So you can see here how you can zoom in,
15:10
zoom out of these charts,
15:11
and you can even send the data from this interactive report
15:13
to our internal charting tool,
15:15
where you can make further modifications on the fly.
15:18
Before handing it over to Santi, I want to speak a bit to how PAT gets better
15:22
as you use it.
The Teach button: autonomous benchmark creation and PR generation
15:24
There are two primary ways in which this happens.
15:26
The first is the autonomous one that Brendan alluded to earlier, where we have agents reviewing
15:30
completed conversations looking for ways in which PAT can get smarter.
15:34
And the second one — and the one we'll be showing here — is the more explicit option, where a
15:38
user can kick off this learning process within the context of an analysis if they think there
15:42
is something to be learned from their interaction with PAT.
15:45
So right here, we just have the user asking for a different set of visualizations.
15:49
Note the user didn't say anything was wrong — they just wanted a different perspective that
15:53
they thought was important to answering the question at hand.
15:56
If they think that PAT should have produced or suggested this set of visualizations from
16:00
the jump, they can click the Teach button, which will then spawn an agent to go through
16:04
the conversation looking for things like behavioral mistakes, context gaps, or user steering that
16:09
can be front-run.
16:11
The user is then able to modify this or send it as-is, and when they submit it, what happens is:
16:16
first, an agent on the back end will create a benchmark that we expect to fail. This shows
16:20
that we can reproduce this poor behavior. It will then iterate on our context repositories
16:25
or the harness itself until that benchmark passes. And then after confirming that by making
16:29
this benchmark pass, we didn't cause the rest of our suite to fail, we get a Slack message
16:33
with the pull request, including the changes the agent wants to make to PAT. And the thing
16:37
this does is that the next time a human comes to PAT with a similar question, we expect them
16:41
to get the better version of PAT right out of the box. So now I'd like to hand it over
16:45
to Santi for the technical overview.
16:48
[APPLAUSE]
16:48
Hello, everyone.
16:51
Thanks, Michael.
16:52
I'm Santi, the technical lead for the Pocket Analyst Tool.
16:54
I'm sure many of you in the crowd
16:56
are building coding agent products just like we are.
16:58
And it's really hard to build one.
17:00
Coding agents are really fickle and unpredictable,
17:03
they often make mistakes.
17:04
And when you're really unlucky,
17:05
they'll go off the rails and try to nuke your data
17:07
and all the rest of it.
17:09
And so it's already hard to build a good product
17:11
that people like, but then it's really hard to build a product
17:13
they want to embed into their daily workflows.
17:16
At a hedge fund, we're trying to trade billions of dollars,
17:19
and so we can't have just vibe-coded analysis
17:21
be the underpinning of how these analyses go.
17:24
My background is in compiler theory
17:27
and programming language design.
17:28
Compilers have a very similar footprint of requirements:
17:33
they're fully deterministic, fully correct,
17:36
and reliable.
17:37
You can't have an off-by-one error
17:38
when you're flying a plane, for example.
17:40
And there's a similar shape here.
17:42
A compiler takes user code and compiles it down to something
17:45
like JavaScript, and a coding agent takes a user prompt or plan
17:48
and compiles it down to Python.
17:51
We really like this approach, and I don't have a lot of time
17:54
today,
17:54
but we're going to focus on this as a learning that maybe you
17:57
might be able to take home to your own work.
17:59
We're going to start with the chat agent.
18:01
The goal here is for the chat agent and the user
18:04
to come to a common understanding of what they're
18:06
trying to accomplish.
Santi Weight: treating coding agents as a compiler problem
18:08
The chat agent is implemented in LangGraph.
18:10
We primarily use it for persistent state.
18:12
It has out-of-the-box cancellations and continuations.
18:16
We used to manage that stuff ourselves
18:18
with a much worse effect.
18:20
The chat agent has access to tool calls.
18:22
Michael called some of these out.
18:23
So there's data series search, unstructured search,
18:26
and each of these would be a tool call themselves.
18:28
And then once the chat agent knows all the data
18:30
it needs for its analysis,
18:31
it's going to make a plan and invoke a tool call
18:34
to a sub-agent, which is our coding agent.
18:36
And that's going to produce a Python-Pandas analysis.
18:39
So why would you separate your two agents?
18:42
Early on, we decided that our investors are not programmers
18:45
by trade — they care about investment.
18:47
So we decided to keep the chat purely
18:49
about investment content.
18:51
And the result is that we have a product where coding
18:53
is a pure implementation detail.
18:55
From the chat,
18:57
you can't tell that there's code under the hood.
19:00
Other happy accidents: you get clean context,
19:03
so each agent becomes specialized
19:04
at its job and naturally improves.
19:07
And we get to tailor the chat experience a lot.
19:10
What we're going to talk about now
19:12
is that our investment domain context is really high quality.
19:16
We teach the chat agent how to talk
19:19
like a Bridgewater investor.
19:21
There's a lot of jargon to teach it.
19:23
And so the user and the agent both talk to each other
19:25
like coworkers at Bridgewater.
19:28
We also let our investors contribute —
19:30
Michael was showing that — contribute like a developer
19:32
on the codebase.
19:33
And this is a pretty good point.
19:36
Your user is better at writing context than you are,
19:38
most likely.
19:39
And so having low ego about it and letting them contribute
19:41
directly is a good way to win.
Chat agent architecture in LangGraph and why coding is a pure implementation detail
19:44
The last point I make about the chat: we teach the chat
19:47
agent not just context — which you end up with this nebulous
19:50
context that is very high-information but doesn't really
19:52
feel like a workflow.
19:54
Instead, we have step-by-step guides for the
19:57
agent on how to handle certain types of analyses.
19:59
And it feels much more like a product at that point.
20:01
Dependable workflows.
20:04
The rest of the talk is about my personal favorite part,
20:06
which is the coding agent.
20:08
This is a high-level architecture diagram
20:10
of the coding agent.
20:11
Everything you see here is actually just Python code.
20:13
It's influenced by LangGraph,
20:15
but there's no agentic orchestration.
20:17
Everyone's taking photos. That's great.
20:20
We're going to start with the left,
20:21
which is the analysis plan that the chat agent makes.
20:27
The analysis plan is broken up into tasks.
20:30
Each task maps approximately to one Python function
20:33
that's going to calculate a data frame.
20:35
Here's an example schema.
20:36
It gets a name, a description of what to calculate,
20:40
and then structural and semantic information
20:43
about the data frame that should come out.
20:45
We expect every task to deterministically compile
20:49
via LLM to a piece of code.
20:51
So two LLMs operating on the same task
20:53
should produce code that, when run, is semantically equivalent —
20:56
the same output values, exactly the same.
20:59
The result is that our analysis plan
21:01
isn't just a to-do list like you'd see in Claude Code.
21:03
Instead, we think of it
21:05
as a natural language Python project.
21:06
And because we have so much detail,
21:08
now we're going to go into code gen
21:10
and we can apply some fancy techniques.
The natural language Python project: deterministic tasks and parallel LLM gen
21:13
The first thing: we split it into tasks
21:16
and then do parallel LLM generation.
21:19
And because our plan is so detailed,
21:22
a visualization task at the end of the plan
21:24
already knows everything it needs
21:25
to consume from code generation that hasn't yet been completed
21:28
for loading data, say.
21:31
And when we compare this to Claude Code,
21:33
you can see that on average — for the same context and same plan — we're about
21:38
four times faster at generating code. But then we have this hyper-scaling, so a 20-task
21:42
plan takes the same amount of time as a three-task plan. So now we have code and we're
21:47
going to execute it. You'd want to just execute the code naively, but sadly, LLMs today
21:53
aren't perfect on our tasks, so they don't normally one-shot it. Instead, what we do is
21:58
take the task that came in from the plan and the code that was generated from
22:01
the task, then run the code, compare it to the task, see if it's correct,
22:06
and if it's not, edit the code and keep going until we're done.
22:10
The first thing we do on the code is static analysis, then figure out the DAG,
22:15
and we apply our validation agents in parallel.
22:18
Here, there are two tasks being validated at the same time.
22:22
So a five-task plan comes down to three layers, and a 20-task plan might be four
22:26
or five layers of validation.
22:28
The main point I want you to take away from this part of the slides is that
22:32
we enforce correctness in the architecture.
22:35
Again, no agentic orchestration.
Validation agents in parallel: enforcing correctness in the architecture
22:37
This is regular Python code, so the guardrails are really hard, and the agents cannot forget
22:41
to validate.
22:42
They are forced to validate.
22:44
The result is that when we run our test suite on any plan, 95% of
22:49
the time, the code that comes out is exactly the same for two different agents.
22:53
So it's essentially a deterministic coding agent.
22:57
And then because we have such a reproducible agent,
23:00
as we're scaling and hill climbing
23:02
and evaluating, we have something much more dependable
23:04
than vibes-based or LLM-as-judge evals.
23:10
Cool.
23:10
One more topic I'm going to touch on,
23:13
which is the execution layer.
23:15
Normally, coding agents invoke their code themselves.
23:17
They generate code, and then call it themselves
23:19
via terminal.
23:20
There are a couple of trade-offs here.
23:22
That's high latency with the tool calls,
23:23
and as you've all experienced,
23:25
they'll sometimes get lost along the way.
23:28
So instead, we run the code for the LLMs.
23:32
We do a classical static analysis pipeline
23:35
where we inject caching annotations into the Python code
23:37
to avoid re-execution and run it through a custom framework.
23:42
This is an example benchmark we have
23:44
for Claude Code invoking its own code versus Pocket Analyst.
23:48
We're faster
23:50
because we never double-load data
23:51
or double-execute intermediates.
23:54
But the actual win is not on the first time you run the code,
23:56
it's the second time.
23:57
Oh, there we go.
23:59
This is a benchmark where we take the last chart in a plan
Execution layer: static analysis, caching annotations, and near-instant re-runs
24:03
and just change the name.
24:04
Claude Code is going to go and rerun all the code —
24:07
basically the same amount of time,
24:08
though it is faster at editing the code.
24:10
But Pocket Analyst basically has instantaneous code execution
24:12
for the second round.
24:13
And this means that when you're working on the product
24:15
as an investor, you can make small tweaks
24:17
to your investment analysis without
24:19
the overhead of a regular iteration.
24:25
OK, we're out of time.
24:26
We had many learnings, but unfortunately
24:27
we can only cover these.
24:29
The first takeaway: we really believe
24:32
in specializing our agents.
24:33
We don't really believe in generic, powerful agents.
24:37
They make really cool demos.
24:38
I'm sure many of us have given them.
24:40
But it's really hard to make that a daily workflow
24:42
that you can depend on.
24:44
Instead, we take often very narrow workflows
24:46
and benchmark them very heavily,
24:48
and then we hill climb those benchmarks.
24:52
You can then compound the agents after the fact,
24:53
but it's harder to go back the other way.
24:56
And this last thing is kind of a thought exercise —
24:58
something I hope is exciting and someone might take away:
25:01
think of agentic coding as a compiler problem,
25:03
not an agentic problem.
25:06
Compilers have been around for decades
25:08
and they have a ton of techniques
25:09
for how to generate code more reliably, correctly,
25:11
and deterministically.
25:13
We'd love to chat about this.
25:16
With that, I'd like to shout out our direct team.
25:19
There were many others, but this is the direct team.
25:22
Thank you.
25:27
We're going to be outside for the AMA.
Three takeaways: specialize agents, benchmark narrow workflows, think compiler
25:29
We would really love to chat and talk about it
25:32
and see if you're excited by the problems too.
25:34
See you all around tonight.
25:36
Thank you so much.
25:38
[APPLAUSE]