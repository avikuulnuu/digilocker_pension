DigiLocker API Postman Automation Suite
=======================================

This package contains everything you need to automate end-to-end DigiLocker API testing in Postman, including HMAC/KeyHash calculation and request chaining.

CONTENTS:
---------
- digilocker.postman_collection.json : Postman Collection with pre-request and test scripts
- README.txt                        : This file (instructions)

SETUP:
------
1. Import the Collection:
   - In Postman, click "Import" > "Upload Files" and select digilocker.postman_collection.json.

2. Create a Postman Environment with these variables:
   - api_key   : Your DIGILOCKER_API_KEY
   - issuer_id : Your DIGILOCKER_ISSUER_ID
   - base_url  : e.g., http://localhost:8000

3. Edit the request body parameters in the Pull URI request as needed for your test document.

USAGE:
------
- The HMAC and KeyHash are calculated in the pre-request script using the final request body (with your input values).
- After sending the Pull URI request, the test script extracts the <URI> from the response and sets it as the 'uri' environment variable.
- The Fetch Document request uses this 'uri' variable automatically.

TIPS:
-----
- You can run the collection in sequence for full automation.
- Use the Postman Console (View > Show Postman Console) to debug variables and scripts.

For any issues, check the scripts in the collection or contact your developer support.
