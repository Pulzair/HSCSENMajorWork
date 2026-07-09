
SOFTWARE ENGINEERING
Major Work → Part A: Design Breakdown

Browser-Based Multiplayer Turn-Based Territory Strategy Game

Year 12 Software Engineering  2026

1. Needs Analysis
1.1 Problem Definition
Within contemporary society, adolescents are experiencing a commonly accepted decline in social interaction. While the teenagers of today are more digitally connected than any generation prior, the quality of these connections is deteriorating. A study found that "emotional closeness [has] declined by 22% since 2010" (Twenge, 2024). This seemingly paradoxical situation represents a genuine social problem for adolescents.
As a response to this, digital gaming has become one of the primary spaces where teenagers seek social connection. Research found that "93% of teenagers said they played video games at least once in the past month" (Digital Wellness Lab, 2024), with "72% of teens who play video games say that a reason why they play them is to spend time with others" (Gottfried, 2024). This demonstrates that games surpass mere entertainment and that they are a primary social construct for young people.
Of the available game genres, strategy games are uniquely suited to address this problem. Unlike action or sports games, where the outcome is heavily reliant on motor skills, strategy games reward deep decision-making through planning, negotiation, and opponent modelling, all being cognitive activities that produce goal-oriented shared experiences identified as characteristic of deep social interaction. Furthermore, the inclusion of a diplomacy system directly simulates negotiation, alliance and civic responsibility, helping develop social skills while aligning with the community, civics and citizenship graduate profiles that this task focuses on.
In addition to this, the game will be browser-based to facilitate ease of use, especially within a school setting where digital distribution platforms like Steam are restricted.
The following lists the problems that current solutions face:
Problem 1: Monetisation barriers
The current browser-based strategy games are built around a hyper-aggressive free-to-play (F2P) monetisation model. Competitive viability within the game is often contingent on in-app purchases, which creates inequality between players, a problem particularly pronounced across different socioeconomic backgrounds. 
Problem 2: Time investment requirements
Existing titles require extensive time commitment either to become competitively viable or to simply complete a match. Forge of Empires, for example, is built around weeks-long city progression, and Civilisation VI has a required play time of upwards of 6 hours per game.
Problem 3: Mechanical stagnation
The browser strategy genre has seen little to no innovation in recent years. Most titles replicate the simple resource-gathering and territory-expansion game loop established decades ago. Without differentiation in features, these games remain unable to attract new players.
These three problems together demonstrate the presence of a genuine, identifiable need and opportunity.
1.2 Proposed Solution
The proposed solution is a web-based multiplayer turn-based territory strategy game targeting high school students aged 13 to 18. The system includes five key innovations, the combination of which is currently absent from market competitors:
Simultaneously delayed orders: rather than alternating turns, all players submit their moves secretly. Orders are revealed and resolved simultaneously, eliminating the information advantage of moving second and rewarding strategic prediction over reaction speed.
Layered map system: the game world consists of three distinct explorable layers — land, underground and sky. Each layer has unique properties. Units on different layers cannot engage directly unless specific mechanics are used.
Finite resource pool: fixed total resources on the map. Aggressive expansion depletes the global supply, creating strategic tension between early aggression and long-term sustainability.
Diplomacy system: players may form alliances, trade resources and sign non-aggression agreements enforced by the game engine. Breaking agreements affects reputation stats. This directly simulates negotiation and civic responsibility.
Dynamic natural events: random natural disaster events that shift the fog of war, destroy terrain, block movement and redistribute resources.
1.3 Competitor Analysis
Name
Type
Key Features
Problems
OpenFront.io
Browser RTS
Free, fog of war, alliances, naval warfare
Real-time format rewards reflexes over strategic thinking; anonymous global matchmaking; single 2D layer only
Forge of Empires
Browser strategy MMO
City building, long-term progression
Weeks-long progression required, heavily monetised, no peer vs peer session play
atWar
Browser strategy
Risk/Civ-style multiplayer, world maps
No private lobby system, no diplomacy enforcement, no session-based format
Territorial.io
Browser IO strategy
Simple territory expansion
Extremely shallow mechanically, no resources, no diplomacy, no fog of war
Civilisation VI
App-based strategy
Deep strategy, diplomacy, layered systems
Requires download and purchase, 6+ hour match length, not browser-based


The closest competitor is OpenFront.io, which shares the browser-based, free-to-play, territorial format. However it differs in three critical ways: it is real-time rather than turn-based, meaning success is partly determined by reaction speed rather than strategic thinking; it targets anonymous global matchmaking at massive scale rather than peer cohort play; and it uses a single 2D map layer with no underground or aerial dimension.
1.4 Stakeholder Analysis
Primary Stakeholders
Players (High School Students, Years 9–12)
Players are the direct end-users. They interact with the game interface to submit orders, manage territories, negotiate diplomacy agreements and track game state across sessions.
Needs:
A fast-loading, no-download browser interface accessible from school devices
Clear visual representation of the layered map and fog of war
Session lengths compatible with school lunch or free periods (15–30 minutes)
Meaningful social mechanics that reward communication and negotiation with known peers
Persistent accounts saving match history and statistics across sessions
A fair, purchase-free competitive environment where outcome is determined by strategy alone

Developer (Project Owner)
As the developer and system owner, I am a primary stakeholder with direct interest in the platform's success.
Needs:
A modular, maintainable codebase accommodating new map types, disaster events and units without restructuring core systems
Scalable back-end architecture handling multiple simultaneous game sessions
Administrative tooling to monitor active games and manage accounts
Secondary Stakeholders
School Administration
Not direct users but influence platform access via school network and device policies.
Needs: Confirmation of no inappropriate content or advertising; compliance with the Australian Privacy Act 1988; minimal network bandwidth consumption.

Parents and Guardians
Indirect interest as the platform is used by minors. Needs: no contact with unknown adults; no monetisation mechanics targeting minors.
1.5 Evidence of Need
Source
Finding
Digital Wellness Lab (2024)
93% of teenagers play video games at least monthly; the majority engage in multiplayer gaming weekly with known peers
Gottfried, J. — Pew Research Center (2024)
72% of teens who play video games cite spending time with others as a primary reason for playing
Twenge (2024)
Emotional closeness among teenagers has declined 22% since 2010 despite increased digital communication frequency
Black Dog Institute (2024)
Rising social isolation among Australian 14–18 year olds; structured peer activities identified as a protective factor
Competitor analysis
No existing browser-based strategy game combines simultaneous turn ordering, a three-layer map, dynamic disasters, finite resources and a diplomacy system at a school-appropriate session length and price point

1.6 Essential vs Desirable Features
Feature
Priority
Justification
User account system
Must-have
Required for persistent match data and player identification
Private lobby system
Must-have
Core part of the school peer cohort model
Layered map (land, underground, sky)
Must-have
Primary mechanical differentiator
Simultaneous delayed orders
Must-have
Primary mechanical differentiator
Fog of war
Must-have
Fundamental to strategy game design
City building, territory expansion, unit combat
Must-have
Core mechanics of any strategy game
Natural disaster events
Should-have
Mechanical differentiator; game functions without it
Finite resource pool
Should-have
Adds strategic depth; game functions without it
Diplomacy and alliance system
Should-have
Key social mechanic; complex to implement
Match history and statistics
Should-have
Supports replayability and engagement
Leaderboards
Could-have
Engagement feature, not core
Cosmetic customisation
Could-have
No gameplay impact
Replay system
Could-have
High development cost, low priority

2. Feasibility Assessment
2.1 Scheduling Feasibility
The design phase of this task takes place over approximately 8 weeks, a large portion of which runs concurrently with other Year 12 subjects. At an estimate of 4 hours per week during term (6 weeks) and 8 hours per week during holidays (2 weeks), the total available time for the design phase is 40 hours. This is sufficient to produce a comprehensive design document, provided the work is spread evenly across the 8 weeks.
The implementation phase (Part B) occurs over approximately 4 months following the finalisation of this document. The five core mechanical innovations being simultaneous turns, layered map, fog of war, natural disaster events and the diplomacy system each represent key development challenges. At a conservative estimate of 2 weeks per system, that yields 10 total weeks of development. Given 16 weeks available, this leaves 6 weeks to implement baseline features (unit commands, city development, etc.) along with any desirable features if time permits.
The main scheduling risk lies in Part B. This is mitigated through this design document to avoid over-scoping.
2.2 Technical Feasibility
Known Skills
Skill
Application to this project
HTML and CSS
Front-end interface, page layouts, map display and all visual elements of the game client
Python
Back-end development, server-side game logic, turn resolution algorithms and database interaction
SQL and relational databases
Designing and querying the data model covering users, games, territories, turns and diplomacy agreements
Git and GitHub
Version control, branch management and maintaining a recoverable development history throughout the project


Skills to be Acquired
Skill
Est. Learning Time
Relevance
JavaScript
2–3 weeks
Client-side interactivity, map rendering, back-end communication
Flask (Python web framework)
1 week
Handling HTTP requests, routing and serving the web application from a Python back-end
Flask-SocketIO / WebSockets
1–2 weeks
Real-time simultaneous turn revelation between all connected players; cannot be achieved with standard HTTP alone


This project is technically feasible given the 4-month implementation timeline. JavaScript and WebSockets are the main risks, everything else builds naturally on existing Python and SQL knowledge or is handled by well-documented Flask extensions. The critical mitigation is front-loading JavaScript learning in the first two weeks of implementation before any production code is written.
2.3 Resource and Financial Feasibility
Resource
Minimum (local)
Desirable (cloud)
Cost
Development IDE
VS Code
VS Code
$0
Version control
GitHub Education
GitHub Education
$0
Back-end
Local Flask/Python
Render or Railway (free tier)
$0
Database
Local SQLite
Supabase (free tier)
$0
Domain and SSL
Localhost
Vercel subdomain + auto SSL
$0
Assets and textures
Open licence resources
Open licence resources
$0
Total




$0 


The minimum viable deployment, running entirely on localhost, costs nothing and is sufficient for assessment demonstration purposes. Cloud deployment via Vercel and Supabase is a desirable enhancement. Development will be conducted on an existing personal or school computer; no additional hardware purchases are required.
2.4 Constraints, Risks and Assumptions
Constraints
School network restrictions: WebSocket connections and browser games may be blocked on school networks. This must be tested on the school Wi-Fi early in development and IT must be contacted if necessary.
Free hosting tier limitations: if cloud deployment is used, free tiers impose limits on concurrent users, database storage and monthly bandwidth. These limits are unlikely to be exceeded given the small expected user base.
Simultaneous school load: as a Year 12 student, the project competes for time with other assessment tasks. Available hours will fluctuate, particularly around exam periods.
Risks
Risk
Chance
Impact
Mitigation
WebSocket blocked by school network
High
Medium
Contact IT; fall back to HTTP long-polling if necessary
JavaScript learning gap blocks early implementation progress
Medium
High
Dedicate first two weeks of Part B exclusively to JavaScript before writing production code
Scope creep during implementation
High
Medium
Strictly implement must-have features before beginning should-have features
Layered map rendering too complex
Medium
Medium
Implement as tabbed toggle views as contingency rather than simultaneous 3D render
Free hosting tier limits exceeded
Low
Low
Temporarily upgrade to paid tier for assessment period if needed


Assumptions
Users have access to a modern browser on either a personal or school device
The developer has access to a personal or school laptop capable of running all required development tools
Free-tier cloud services remain available around their current usage limits throughout the assessment period
The teacher acting as client stakeholder is available for at least two feedback sessions during the design phase
3. Requirements Specification
3.1 System Overview
The proposed system is a browser-based multiplayer turn-based territory strategy game. It consists of a front-end client rendered in HTML, CSS and JavaScript, and a Python/Flask back-end managing user accounts, game state, turn resolution and real-time communication between players via WebSockets. The system is accessed entirely through a web browser with no download or installation required.
3.2 Functional Requirements
Functional requirements describe what the system must do. Each requirement is written to be specific and testable.
Authentication and Account Management
ID
Requirement
Priority
FR01
The system will allow users to register an account using a unique username, email and password
Must-have
FR02
The system will reject registration if the username or email already exists in the database
Must-have
FR03
The system will allow users to log in and log out using their email and password
Must-have
FR04
The system will allow users to view and edit their profile and login information
Should-have


Lobby and Session Management
ID
Requirement
Priority
FR05
The system will allow users to create a private game lobby, generating a unique 6-character join code
Must-have
FR06
The system will allow users to join an existing lobby by entering a valid join code
Must-have
FR07
The system will support between 2 and 6 players per game session
Must-have
FR08
The system will allow the lobby host to alter game settings and configure players before starting
Must-have
FR09
The system will prevent a game from starting until a minimum of 2 players have joined
Must-have


Core Gameplay
ID
Requirement
Priority
FR10
The system will render a three-layer map (land, underground, sky), allowing players to switch between layers
Must-have
FR11
The system will implement a fog of war system limiting each player's visibility based on unit locations and historic movement
Must-have
FR12
The system will allow users to issue unit commands (move, attack, build, layer transition) during the order placement phase
Must-have
FR13
The system will allow users to form and develop territories, improving cells within borders and the central district
Must-have
FR14
The system will allow users to create new units
Must-have
FR15
The system will collect all players' moves simultaneously and secretly during each turn's submission phase
Must-have
FR16
The system will reveal and resolve all players' orders simultaneously after the turn timer expires
Must-have
FR17
The system will resolve order conflicts where two or more players target the same territory using the combat resolution algorithm
Must-have
FR18
The system will track and display each player's resource totals, updated after every turn
Must-have
FR19
The system will enforce a finite global resource pool shared across all players
Should-have
FR20
The system will trigger a random natural disaster at random intervals based on a weighted pool of event types
Should-have
FR21
The system will update fog of war, terrain and resource distribution on affected territories following a disaster event
Should-have
FR22
The system will allow users to propose, negotiate and accept diplomacy agreements
Should-have
FR23
The system will enforce active diplomacy agreements for their specified duration
Should-have
FR24
The system will apply reputation penalties to any player who breaks an active agreement
Should-have
FR25
The system will declare a winner and end the game when a victory condition is met
Must-have


Statistics and Administration
ID
Requirement
Priority
FR26
The system will record each completed match, storing the winner, participants, turn count and final scores
Should-have
FR27
The system will display a post-game summary screen to all players
Must-have
FR28
The system will maintain a leaderboard ranking players by win rate or ELO
Could-have
FR29
The system will provide an administrator dashboard to view and manage active sessions and user accounts
Must-have

3.3 Non-Functional Requirements
Non-functional requirements define the quality targets the system must meet. Each includes a concrete, measurable target.
ID
Requirement
Target
Priority
NF01
All page loads and updates must complete on a standard connection
Under 0.2 seconds on a 10Mbps connection
Must-have
NF02
The system will support multiple simultaneous game sessions without performance degradation
Minimum 10 concurrent sessions
Must-have
NF03
If a player disconnects mid-game, their submitted orders and game state will be preserved for their return
Orders preserved for minimum 60 seconds before turn forfeit
Should-have
NF04
All user passwords will be hashed using bcrypt before storage
Minimum cost factor of 10
Must-have
NF05
All client-server communication will be encrypted
HTTPS and WSS (secure WebSocket) only
Must-have
NF06
All user inputs will be validated and sanitised server-side before processing
Zero unsanitised inputs reach the database
Must-have
NF07
The system will collect no personally identifiable information beyond username and email
No additional data fields collected or stored
Must-have
NF08
User data must not be shared with or sold to any third party
No third-party data sharing of any kind
Must-have
NF09
New maps, units and disaster event types will be addable without modifying core game logic
Achievable via configuration files only
Must-have
NF10
The system will function correctly on current versions of Chrome, Firefox and Safari
No plugins or downloads required
Must-have

3.4 System Boundaries
The following are within the system boundary:
User registration, login and profile management
Private lobby creation and join code system
Three-layer map rendering and display
Fog of war calculation and real-time updates
Simultaneous order submission and turn resolution engine
Combat resolution algorithm
Natural disaster event generation and terrain effects
Finite global resource pool tracking
Diplomacy agreement proposal, enforcement and breach detection
Match result recording and post-game summary
Administrator dashboard for account and session management
The following are outside the system boundary:
Email verification or password reset via email
AI opponent logic  
In-game voice communication or free-form chat
Payment processing of any kind
Mobile native applications 
Automated content moderation
Integration with external platforms such as school LMS or social media
4. Data Dictionary and Data Model
4.1 Data Dictionary
A data dictionary provides a comprehensive description of every variable stored or processed by the system. Entries are organised by entity and follow the NSW Software Engineering course specification format.
Entity: User
Variable
Data type
Format for display
Size in bytes
Size for display
Description
Example
Validation
user_id
Integer
NNNNNN
4
6
Auto-incrementing primary key uniquely identifying each user
1042
System-generated, never null, never modified
username
String
XX..XX
Variable (max 32)
32
Player's chosen display name
strat_king99
3–32 chars, alphanumeric and underscores only, must be unique
email
String
XX..XX@XX.XX
Variable (max 254)
254
User's email address used for login
user@gmail.com
Must match email regex pattern, must be unique
password_hash
String
XX..XX
60
60
bcrypt hash of user's password; never stored as plaintext
$2b$10$...
System-generated, cost factor minimum 10, never null
created_at
Date and Time
YYYY-MM-DD HH:MM:SS
4
19
Timestamp of account registration
2026-03-15 09:42:00
System-generated on registration, never null
reputation
Integer
NNN
4
3
Diplomacy reputation score; affects agreement costs and neutral territory behaviour
85
Integer 0–100; defaults to 50 on registration
is_admin
Boolean
T/F
1 bit
1
Whether account holds administrator privileges
FALSE
Defaults FALSE; only modified manually by existing admin


Entity: Game
Variable
Data type
Format for display
Size in bytes
Size for display
Description
Example
Validation
game_id
Integer
NNNNNN
4
6
Auto-incrementing primary key uniquely identifying each game session
307
System-generated, never null
join_code
String
XXXXXX
6
6
Randomly generated uppercase alphanumeric lobby access code
XK4T9R
6 chars, A–Z and 0–9, unique at time of generation
map_id
Integer
NNNN
4
4
Foreign key referencing the map configuration used
3
Must reference a valid map_id in the Map table
status
String
XX..XX
Variable (max 12)
12
Current state of the game session
active
Must be one of: lobby, active, complete
current_turn
Integer
NNN
4
3
Turn number currently in progress
7
Minimum 1; increments by 1 after each resolution
winner_id
Integer
NNNNNN
4
6
Foreign key referencing the winning player's user_id
1042
Null until game status is complete
created_at
Date and Time
YYYY-MM-DD HH:MM:SS
4
19
Timestamp of lobby creation
2026-03-15 10:00:00
System-generated, never null
completed_at
Date and Time
YYYY-MM-DD HH:MM:SS
4
19
Timestamp of game completion
2026-03-15 10:34:00
Null until status is complete
global_resources
Integer
NNNNN
4
5
Remaining total resources in the shared global pool
1450
Must be greater than or equal to 0


Entity: GamePlayer
Variable
Data type
Format for display
Size in bytes
Size for display
Description
Example
Validation
gameplayer_id
Integer
NNNNNN
4
6
Auto-incrementing primary key
88
System-generated, never null
game_id
Integer
NNNNNN
4
6
Foreign key referencing the associated game session
307
Must reference a valid game_id
user_id
Integer
NNNNNN
4
6
Foreign key referencing the associated user account
1042
Must reference a valid user_id
player_colour
String
#XXXXXX
7
7
Hex colour code used to identify this player on the map
#E63946
Must be a valid hex colour, unique within the game
resources
Integer
NNNNN
4
5
Player's current personal resource total
240
Must be greater than or equal to 0; defaults to 0
is_host
Boolean
T/F
1 bit
1
Whether this player created the lobby
TRUE
Only one player per game may have is_host = TRUE
is_eliminated
Boolean
T/F
1 bit
1
Whether this player has been eliminated from the game
FALSE
Defaults FALSE; set TRUE when player loses all territories


Entity: Territory
Variable
Data type
Format for display
Size in bytes
Size for display
Description
Example
Validation
territory_id
Integer
NNNNNN
4
6
Auto-incrementing primary key
512
System-generated, never null
game_id
Integer
NNNNNN
4
6
Foreign key referencing the game this territory belongs to
307
Must reference a valid game_id
map_territory_ref
Integer
NNNN
4
4
Reference to the base territory definition in the map layout JSON
14
Must match a territory entry in the map's layout_json
layer
String
XX..XX
Variable (max 12)
12
The map layer this territory occupies
land
Must be one of: land, underground, sky
owner_id
Integer
NNNNNN
4
6
Foreign key referencing the controlling player's user_id; null if unowned
1042
Null if unowned; must reference a valid user_id if set
resource_value
Integer
NNN
4
3
Resources this territory generates per turn
15
Must be greater than or equal to 0
terrain_type
String
XX..XX
Variable (max 16)
16
Terrain classification affecting movement and combat
mountain
Must be one of: plains, mountain, water, destroyed
has_city
Boolean
T/F
1 bit
1
Whether a city has been constructed on this territory
FALSE
Defaults FALSE
fog_modifier
Floating Point
N.NN
4
4
Visibility modifier applied by natural disaster effects; defaults to full visibility
0.5
Decimal between 0.0 and 1.0 inclusive


Entity: Unit
Variable
Data type
Format for display
Size in bytes
Size for display
Description
Example
Validation
unit_id
Integer
NNNNNN
4
6
Auto-incrementing primary key
2041
System-generated, never null
game_id
Integer
NNNNNN
4
6
Foreign key referencing the game this unit belongs to
307
Must reference a valid game_id
owner_id
Integer
NNNNNN
4
6
Foreign key referencing the owning player's user_id
1042
Must reference a valid user_id
territory_id
Integer
NNNNNN
4
6
Foreign key referencing the territory this unit currently occupies
512
Must reference a valid territory_id
unit_type
String
XX..XX
Variable (max 16)
16
Type classification determining layer compatibility and combat stats
airship
Must be one of: infantry, cavalry, airship, submarine
attack
Integer
NN
4
2
Unit's attack value used in combat resolution
8
Integer between 1 and 20 inclusive
defence
Integer
NN
4
2
Unit's defence value used in combat resolution
5
Integer between 1 and 20 inclusive
health
Integer
NNN
4
3
Unit's current health points; unit removed from game at 0
10
Integer between 1 and 100
layer
String
XX..XX
Variable (max 12)
12
The map layer the unit currently occupies
sky
Must match the layer of its current territory_id


Entity: Order
Variable
Data type
Format for display
Size in bytes
Size for display
Description
Example
Validation
order_id
Integer
NNNNNN
4
6
Auto-incrementing primary key
9823
System-generated, never null
game_id
Integer
NNNNNN
4
6
Foreign key referencing the game this order belongs to
307
Must reference a valid game_id
player_id
Integer
NNNNNN
4
6
Foreign key referencing the submitting player's user_id
1042
Must reference a valid user_id in this game
turn_number
Integer
NNN
4
3
The turn number this order was submitted for
7
Must equal the game's current_turn at submission time
order_type
String
XX..XX
Variable (max 16)
16
The category of action this order represents
attack
Must be one of: move, attack, build, layer_transition
unit_id
Integer
NNNNNN
4
6
Foreign key referencing the unit this order applies to
2041
Must reference a unit owned by player_id
source_territory
Integer
NNNNNN
4
6
Foreign key referencing the territory the unit moves from
512
Must reference a valid territory_id occupied by unit_id
target_territory
Integer
NNNNNN
4
6
Foreign key referencing the destination territory
513
Must be adjacent to source_territory in the map layout
status
String
XX..XX
Variable (max 12)
12
Resolution status of this order
pending
Must be one of: pending, resolved, cancelled; defaults pending
submitted_at
Date and Time
YYYY-MM-DD HH:MM:SS
4
19
Timestamp of order submission
2026-03-15 10:14:22
Must fall within the current turn's submission window


4.2 Entity Relationship Diagram

4.3 Class Diagram

4.4 Data Flow Diagram

5. Methodology Selection and Justification
5.1 Overview of Development Methodologies
Waterfall
Waterfall is a linear, sequential approach to software development in which each phase, requirements, design, implementation, testing and deployment must be fully completed before the next begins. Waterfall works well when requirements are well-understood and unlikely to change, its primary weakness is inflexibility.
Agile
Agile is an iterative, incremental approach organised around short development cycles called sprints, typically one to four weeks in length. At the end of each sprint, a working software increment is produced, reviewed and used to inform the next sprint's priorities. Its strength is adaptability, its main weakness in a student context is the assumption of continuous stakeholder availability for sprint reviews.
WAgile (Waterfall-Agile Hybrid)
WAgile combines structured upfront planning from Waterfall with iterative development cycles from Agile. A thorough requirements and design phase is completed first, providing a stable architectural foundation, after which development proceeds in Agile-style sprints. This preserves the benefits of clear upfront design while retaining the flexibility to adapt implementation decisions as development progresses. WAgile suits projects where the high-level architecture is known but specific implementation details are uncertain.
5.2 Chosen Methodology: WAgile
WAgile is the most appropriate methodology for this project for the following specific reasons:
1. The design phase is mandated by the assessment structure.
2. High-level architecture is known while implementation details are uncertain.
3. Stakeholder access is limited.
4. Single developer context.
5. Part B fidelity requirement (to Part A).
6. Project Plan
6.1 Gantt Chart

Week
1
2
3
4
5
6
7
8
Needs Analysis
















Feasibility Assessment
















Requirements Specification
















Data Model
















Methodology
Selection
















Algorithm Design
















Storyboard
















Tech Stack
















Quality Assurance Plan
















Social Considerations
















Document Review
















Presentation Practice
















Presentation


















7. Algorithm Design
7.1 Algorithm 1: Simultaneous Turn Resolution
This algorithm addresses the core game loop challenge: given orders submitted secretly by all players simultaneously, resolve conflicts, apply movement, calculate combat outcomes and update game state in a deterministic, fair sequence.
BEGIN ResolveTurn (gameState, playerOrders, disasterEvent)
  IF disasterEvent IS NOT null THEN
    FOR EACH territory IN disasterEvent.affectedTerritories
      territory.terrain   <- APPLY_DISASTER_EFFECT(territory, disasterEvent.type)
      territory.resourceValue <- RECALCULATE_RESOURCE(territory)
      territory.fogModifier   <- APPLY_FOG_SHIFT(territory, disasterEvent.type)
    NEXT territory
  ENDIF
  FOR EACH order IN playerOrders
    IF order.sourceTerritory.owner = order.playerID
      AND order.sourceTerritory.layer = order.layer
      AND order.targetTerritory IS adjacent TO order.sourceTerritory
      AND order.sourceTerritory.unitCount > 0
      AND territory NOT destroyed by disaster
    THEN
      ADD order TO validOrders
    ELSE
      ADD (order.playerID, 'Order invalidated') TO resolutionLog
    ENDIF
END ResolveTurn

Design rationale: Disasters are applied before order validation, ensuring that orders targeting destroyed territories are caught. Diplomacy is checked during conflict resolution rather than during validation, because alliance status can change between turn submission and resolution. Resource updates happen after all territorial changes are finalised to avoid double-counting.
7.2 Algorithm 2: Diplomacy Agreement Validator
This algorithm runs at the start of each turn to evaluate all active diplomacy agreements, determine whether terms were honoured or broken in the previous turn, apply reputation consequences and expire agreements that have reached their duration limit.
BEGIN ValidateDiplomacyAgreements (gameState, previousTurnOrders)
  FOR EACH agreement IN gameState.activeAgreements
    IF agreement.turnsRemaining <= 0 THEN
      agreement.status <- 'expired'
      NOTIFY both players of expiry
      CONTINUE
    ENDIF
    agreement.turnsRemaining <- agreement.turnsRemaining - 1
END ValidateDiplomacyAgreements

BEGIN BREACH_AGREEMENT (agreement, breachingPlayerID, breachType, gameState)
  agreement.status    <- 'breached'
  agreement.breachedBy <- breachingPlayerID
  reputationPenalty <- LOOKUP_PENALTY(breachType)
  gameState.players[breachingPlayerID].reputation <-
    gameState.players[breachingPlayerID].reputation - reputationPenalty
  gameState.players[breachingPlayerID].agreementCostModifier <-
    CALCULATE_COST_MODIFIER(gameState.players[breachingPlayerID].reputation)
  NOTIFY agreement.playerA of breach
  NOTIFY agreement.playerB of breach
  ADD (breachingPlayerID, breachType, currentTurn) TO gameState.diplomacyLog

END BREACH_AGREEMENT

Design rationale: The validator runs as a pre-turn process before new orders are submitted, so players can see their current agreement status before deciding their next move. Breach types are separated because non-aggression breaches are detectable from order history, while alliance breaches require an explicit player action. 
8. UI/UX Storyboards

8.2 Accessibility Considerations
All interactive elements must meet a minimum touch target size 
Player colours on the map must be distinguishable to users with colour blindness
All form fields must have visible labels, not just placeholder text
9. Back-end Architecture
9.1 Technology Stack
Layer
Technology
Justification
Front-end
HTML, CSS, JavaScript
Mandated by the course. 
Back-end
Python 3 with Flask
Python is mandated by the course. 
Real-time communication
Flask-SocketIO (WebSockets)
Standard HTTP request-response cannot support simultaneous turn revelation to all clients. 
Database
SQLite (local) / PostgreSQL (cloud)
SQLite requires no server process thus is ideal for local development and assessment demonstration. 
Version control
Git and GitHub
All source code tracked in a private repository. 
Deployment 
Localhost
Zero cost, fully sufficient for demonstration purposes.
Deployment (desirable)
Render or Railway + Supabase
Free-tier cloud hosting allowing peers to play from their own devices without a shared local network.

9.2 Front-end / Back-end Interface
The system uses two communication protocols between client and server:
HTTP REST API
WebSocket (Socket.IO) 
9.3 Error Handling Strategy
All Flask routes return structured JSON error responses using standard HTTP status codes. 
HTTP Code
Scenario
Handling
400
Invalid input
Server returns validation errors; client displays inline field-level messages
401
Unauthenticated request
Client redirects to login page
403
Unauthorised action 
Server returns 403; client shows notification
404
Resource not found 
Client shows 'Lobby not found' message


9.4 Security Engineering
Password hashing: all passwords are hashed using bcrypt with a minimum cost factor of 10 (via Flask-Bcrypt) before storage. Plaintext passwords are never written to the database or logged.
Input validation and sanitisation: all user inputs are validated server-side using Flask-WTF or manual schema checks before any database operation.
Session management: Flask sessions use a cryptographically signed secret key where sessions expire after 24 hours of inactivity.
HTTPS and WSS: all production traffic is transmitted over HTTPS and secure WebSocket (WSS). Localhost development uses HTTP; cloud deployment enforces HTTPS via Vercel/Render auto SSL.
Role-based access control: admin-only routes are decorated with a custom @admin_required decorator that checks the is_admin flag on the session user before processing the request (or similar functioning variables).
Rate limiting: Flask-Limiter is applied to the registration and login endpoints to mitigate brute-force attacks (maximum 10 requests per minute per IP).
10. Quality Assurance Plan
10.1 Quality Criteria
Criterion
Measurable Target
Relevant Requirement
Performance
Page loads and turn resolution complete in under 0.2 seconds on a 10Mbps connection
NF01
Scalability
System supports 10 simultaneous game sessions without degradation
NF02
Security
No unsanitised inputs reach the database and all passwords are bycrpt
NF04, NF05, NF06
Privacy
No data collected beyond username and email
NF07, NF08
Reliability
Disconnected players' game state preserved for minimum 60 seconds
NF03
Usability
New user begins first game within 10 minutes
FR03, NF10
Maintainability
New map types and disaster events addable via configuration without modifying core game logic
NF09
Compatibility
Fully functional on current Chrome
NF10

10.2 Testing Strategy
Functional Testing
Requirement
Test Action
Expected Result
FR01 Registration
Submit registration form with a valid unique username, email and password
Account created; user redirected to dashboard
FR03 Login
Submit valid email and password
Session created; user redirected to dashboard
FR05 Create lobby
Click Create Game while logged in
Lobby created with a unique 6-character join code displayed
FR16 Turn resolution
All players submit orders; timer expires
All orders resolved simultaneously; updated game
FR24 Diplomacy breach
Player attacks a territory owned by an ally
Reputation penalty applied; agreement status updated
FR25 Win condition
Player achieves majority territory control
Winner declared; post-game summary displayed

Boundary Testing
Boundary testing targets the edges of valid input ranges. Key boundary cases are:
Input
Boundary Cases
Expected Behaviour
Players per lobby
1 player (below minimum), 2 players (minimum), 6 players (maximum), 7 players (above maximum)
Below minimum: Start Game button disabled. Above maximum: Join request rejected with error message.
Turn timer
0 seconds remaining (timer expires), 1 second remaining
At 0 seconds: order submission closed; resolution triggered immediately.
Global resource pool
1 resource remaining, 0 resources (depleted)
At 0: resource income set to 0.


10.3 Compliance and Legislative Requirements
Legislation / Standard
Relevance to this project
Australian Privacy Act 1988 (Cth) and Australian Privacy Principles (APPs)
The system collects email addresses from users who may be minors. APP 1 requires a privacy policy. APP 3 limits collection to what is necessary. APP 11 requires reasonable security measures. The system complies by collecting only username and email, using bcrypt hashing, and never sharing data with third parties.
Children's Online Privacy Protection (general principle, Australian context)
The platform targets users aged 13–18. No sensitive personal data (address, phone, date of birth) is collected. No advertising or third-party tracking is present.
WCAG 2.1 (Web Content Accessibility Guidelines)
The interface must meet minimum accessibility standards: sufficient colour contrast ratios, minimum touch target sizes of 44x44px, keyboard navigability and visible focus indicators.
Copyright Act 1968 (Cth)
All map assets, sound effects and graphical elements must be either original works or sourced from open-licence repositories (e.g. Creative Commons). No third-party IP is incorporated without appropriate licensing.
NSW Cybersecurity Policy (if deployed on school infrastructure)
If the system is deployed on school servers or accessed via school accounts, it must comply with the school's network use policy and any relevant NSW Department of Education data governance requirements.

11. Social, Ethical and Communication Considerations
11.1 Social and Ethical Analysis
Privacy and Data Handling
The platform collects only the minimum data required to function: a username, an email address and a hashed password. No location data, device identifiers, browsing history or behavioural analytics are collected or stored. Match history and game statistics are stored but contain no personally identifiable information beyond the username. Users retain the right to request account deletion, which will remove all related data from the system.
Accessibility and Inclusion
The game mechanics are intentionally designed to minimise skill barriers outside of strategic thinking. Visual accessibility is addressed through the use of territory labels and patterns supplementing colour coding, so players who are colour blind are not disadvantaged. 
Online Safety and Appropriate Use
The platform uses a private lobby system with join codes so players can only enter a game if they have been given the code by someone they know. 
Intellectual Property
All game assets will be either original works created for this project or sourced from open-licence repositories. No commercial game assets will be reproduced. 
Equity and Socioeconomic Considerations
The platform is free to access with no in-app purchases, subscriptions or premium features. 
11.2 Communication Plan
Client Engagement
The teacher acts as the primary client stakeholder for this project. Teacher will be contacted throughout in order to gain feedback in Part B.
Feedback Collection
In addition to teacher feedback, peer users (classmates) will be invited to complete short structured playtesting sessions during Part B. After each session, testers complete a brief google survey. Responses are collated and used to prioritise fixes in the following development sprint.
Scope Negotiation
The priority framework established in the Requirements Specification governs scope decisions throughout the project. If implementation time is insufficient to complete all should-have features, the deferred features are documented in the Part B submission as future work. 

