# MERN stack

## What the MERN stack is

MERN is a set of four JavaScript technologies used together to build a web application: MongoDB, Express, React and Node.js. All four use the JavaScript language, so one language runs in the database queries, on the server and in the browser.

MongoDB is a document database. It stores data as JSON-like documents, called BSON, grouped in collections. A document in a collection can have fields that another document does not have, so no fixed table schema is required.

Express is a minimal web framework that runs on Node.js. It receives HTTP requests, matches them to routes such as GET /api/users, runs middleware functions in order, and sends back a response.

React is a JavaScript library for building user interfaces from components. A component is a function that returns JSX, and React updates the page efficiently when the component's state or props change. React runs in the browser and is the front end.

Node.js is a runtime that runs JavaScript outside the browser, on a server. It is built on the V8 engine and handles many connections with an event loop and non-blocking input and output.

## How a request moves through MERN

The user does something in the React front end, for example submitting a form. React sends an HTTP request to the Express server using fetch or axios. An Express route handler running on Node.js reads the request, uses a library such as Mongoose to query MongoDB, and receives the data. The server sends a JSON response, and React stores it in state and re-renders the page with the new data. This client and server split, communicating over a REST API with JSON, is the core pattern of the stack.

## Common mistakes with the MERN stack

Thinking that MongoDB is the server: it is only the database. The server is Express running on Node.js.

Mixing up the front end and back end: React runs in the browser, while Express and Node.js run on the server.

Putting database passwords in the React code, which anyone can read in the browser. Secrets belong in environment variables on the server.

Forgetting to enable CORS on the Express server when React runs on a different port.

Mutating React state directly instead of calling the setter function.
