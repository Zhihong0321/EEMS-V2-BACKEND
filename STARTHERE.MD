Project Spec

Name : Eternalgy EMS.


Core Component :

1. EMS Dashboard (Frontend)
2. Simulator Energy Meter
3. POSTGRES Database.
4. EMS Backend, ( received data, process data )



Core Logic
1. Simulator on a browser page, with configuration, and simulate energy reading and sent to EMS's postgres DB
2. EMS Frontend will display the data from POSTGRES.


Core Purpose.

1. the EMS has a main purpose, to let user manager their 30mins block usage level. ( to avoid excessive PEAK Usage charges. )
2. fixed 30mins block start from 12.00am
3. each block, user can set a Kwh PEAK Target.
4. based on the energy reading, calculate current 30min block accumulated usage (kwh)
5. when usage reaches 80% of the target for the active block, emit an alert-ready signal so the UI can decide how to notify the user (WhatsApp, email, etc.).

#######

The SImulator Meter :
Auto Usage mode :
1. can simulate a factory energy usage.
2. send reading interval 15sec.
3. can set simulate usage + volatility

Manual Usage Mode
4. give user a option to simulate usage with a slider. ( vertical slider, updown, user can slide updown, and generate energy reading every second based on slider )
5. in this mode, every second reading = 15second in real life, so the reading data are generate, the time should be fast forward 15x.

Let user set the following in Simulator:
- Simulator Name, Simulator Meter Target Peak.
- in DB, we should create new Simulator profile based on above data
- when user open the simulator meter page, it should prompt user the existing Simulator Profile to select, and continue to simulate
- OR, user can create a new simulator. and run meter simulation

Remember, the Energy Reading data are related to Simulator.

#######


The EMS Frontend (dashboard)
- The Welcome page = showing available Simulator Meter Profile
- when click, enter Simulator Meter Dashboard
- Showing the Latest 30mins block from the reading Data.
- Plot the chart. Y=kwh, X=30sec, so there will be 60 line chart. for 30min box
- also in the dashboard, below the latest 30mins chart. show last 10, 30mins small box ( showing accumulated usage vs targeted usage kwh )
- if the simulator is running, and generating new data, the dashboard should auto refresh if new data received.


#######

Development and Deployment

- Push to Github
- Railway trigger redeploy
- Railway service already linked with a POSTGRES
- IMPORTANT, KEEP THING SIMPLE, NO OVERENGINEER STUFF. I WANT SMOOTH EASY DEVELOPMENT IN PROTOTYPING PHASE.
- I WANT EASY AND SIMPLE DEPLOYMENT PROTOCOL. 


Question
- now is Prototype phase. but when in Production Phase, we will deploy REAL Energy Meter that communicate with MQTT protocol.
- would it be very troublesome to refactor the Frontend , and backend to work with MQTT protocol meter?
- Do you have other question?
