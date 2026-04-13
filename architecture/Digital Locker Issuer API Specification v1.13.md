# Issuer API Specification Version 1.13 

May 2024 

A Digital India Initiative National e-Governance Division. Department of Electronics and Information Technology. 

Issuer API Specification 

## **Revision History** 

|**Version **|**Date**|**Comments**|
|---|---|---|
|1.0|15/01/2016|Release ofversion 1.0|
|1.1|11/04/2016|AddedDocType elementin PullURI RequestAPI|
|1.2|01/06/2016|Added Aadhaar relatedparameter details|
|1.3|20/07/2016|Added support to accept certificate metadata in Pull<br>DocumentAPI.|
|1.4|29/11/2017|Added support to share Aadhaar photograph in Pull URI<br>Request API and introduced a Pending response status<br>in Pull Response.|
|1.5|19/07/2018|Updated Pull URI Request and Pull Doc Request to<br>support machine readable certificate data.|
|1.6|07/08/2018|Updated the description of Pull URI Request API for<br>Aadhaar based Pull functionality. Added API<br>configurationdetails.|
|1.7|30/10/2018|Added Aadhaar, Name and DOB  parameters in Pull<br>DocumentAPI.|
|1.8|12/08/2019|Changed DataContent tag to include base64 encoded<br>xmlcontent ofcertificate data.|
|1.9|26/06/2020|Added DigiLockerId as a default parameter to Pull URI<br>Request andPull DocumentRequestAPIs.|
|1.10|04/08/2020|Addedx-digilocker-hmacparameter in Pull URI and Pull<br>Doc Requests for authentication.|
|1.11|26/03/2021|Added Name, DoB, Gender, Mobile and Photograph in<br>Pull URI Response API so that the name matching can<br>be performed on DigiLockerside.|
|1.12|15/09/2022|DataContent has become mandatory. Removed<br>Aadhaar, Name and DOB  parameters from Pull<br>DocumentAPI.|
|1.13|21/05/2024|RemovedPull DocumentRequestAPI.|



1 

Issuer API Specification 

## **Table of Contents** 

|**Table of Contents**|**Table of Contents**|
|---|---|
|Revision History ....................................................................................................................................... 1||
|1.|Introduction ..................................................................................................................................... 3|
|2.|Digital Locker System Overview ...................................................................................................... 3|
|3.|Key Terminology .............................................................................................................................. 3|
|4.|On-Boarding Flow ............................................................................................................................ 5|
|5.|Document Codification Scheme ...................................................................................................... 5|
||5.1<br>Unique Document URI............................................................................................................ 5|
||5.2<br>Issuer ID (mandatory) ............................................................................................................. 5|
||5.3<br>Document Type (mandatory) ................................................................................................. 6|
||5.4<br>Document ID (mandatory) ..................................................................................................... 6|
|6.|Document Issuance Flow ................................................................................................................. 7|
|7.|E-Document Specifications .............................................................................................................. 7|
||7.1<br>Document URI ........................................................................................................................ 7|
||7.2<br>Document Owner ................................................................................................................... 7|
||7.3<br>Document Format .................................................................................................................. 8|
|8.|Issuer APIs ........................................................................................................................................ 8|
||8.1<br>Pull URI Request API ............................................................................................................... 8|
||8.1.1<br>Pull URI Request Format .................................................................................................... 8|
||8.1.2<br>Pull URI Request Elements ................................................................................................. 9|
||8.1.3<br>Pull URI Response Format ................................................................................................11|
||8.1.4<br>Pull URI Response Elements ............................................................................................11|
||8.1.5<br>Configuration of Pull URI API in DigiLocker Partner Portal ..............................................13|



2 

Issuer API Specification 

## Di ital Locker Issuer API S ecification g p 

## **1. Introduction** 

This document provides detailed specification of the Digital Locker Pull APIs. The Pull model of integration with Digital Locker enables a Digital Locker user to search a document/certificate from issuer repository and fetch (pull) it into Digital Locker. The issuer departments can use these APIs for the documents that are not Aadhaar seeded. For Aadhaar seeded documents, please refer to Dedicated Repository API Specification of Digital Locker. This document assumes that the reader is aware of Digital Locker application functionality and has read the Digital Locker Technical Specification (DLTS) available in Technical Specification section of Digital Locker Resource Center at https://digitallocker.gov.in/resource-center.php. 

## **2. Digital Locker System Overview** 

The proposed architecture of the Digital Locker system is described in “Digital Locker Technical Specifications (DLTS)” document. Digital Locker system consists of e-Documents repositories and access gateways for providing an online mechanism for issuers to store and requesters to access a Digital Document in a uniform way in real-time. 

## **3. Key Terminology** 

1. _**Electronic Document or E-Document**_ – A digitally signed electronic document in XML format issued to one or more individuals (Aadhaar holders) in appropriate format compliant to DLTS specifications. Examples: 

   - Degree certificate issued to a student by a university. 

   - Caste certificate issued to an individual by a state government department. 

3 

## Issuer API Specification 

   - Marriage certificate issued to two individuals by a state government department. 

_**2. Digital Repository –**_ A software application complying with DLTS specifications, hosting a collection (database) of e-documents and exposing a standard API for secure real-time access. 

   - While architecture does not restrict the number of repository providers, it is recommended that few highly available and resilient repositories be setup and encourage everyone to use that instead of having lots of repositories. 

_**3. Digital Locker –**_ A dedicated storage space assigned to each resident, to store authenticated documents. The digital locker would be accessible via web portal or mobile application. 

_**4. Issuer –**_ An entity/organization/department issuing e-documents to individuals in DLTS compliant format and making them electronically available within a repository of their choice. 

5. _**Requester –**_ An entity/organization/department requesting secure access to a particular e-document stored within a repository. Examples: 

   - A university wanting to access 10th standard certificate for admissions 

   - A government department wanting to access BPL certificate 

   - Passport department wanting to access marriage certificate 

_**6. Access Gateway –**_ A software application complying with DLTS specifications providing an online mechanism for requesters to access an e-document in a uniform way from various repositories in real-time. 

   - Gateway services can be offered by repository providers themselves. 

   - While architecture does not restrict the number of repository providers, it is suggested that few resilient and highly available central gateway systems be setup and requesters can signup with any one of the gateways for accessing documents in the Digital repositories. 

7. _**Document URI –**_ A unique document URI mandatory for every document. This unique URI can be resolved to a full URL to access the actual document in appropriate repository. 

   - Document URI is a persistent, location independent, repository independent, issuer independent representation of the ID of the document. 

   - The existence of such a URI does not imply availability of the identified resource, but such URIs are required to remain globally unique and persistent, even when the resource ceases to exist or becomes unavailable. 

   - While document URI itself is not a secret, access to the actual document is secure and authenticated. 

4 

Issuer API Specification 

## **4. On-Boarding Flow** 

**==> picture [454 x 193] intentionally omitted <==**

**----- Start of picture text -----**<br>
Create<br>Get Issuer ID Document  Generate URI<br>type<br>Create  REST<br>Map URI with<br>based Pull URI<br>e-Document<br>Request API<br>**----- End of picture text -----**<br>


## **5. Document Codification Scheme** 

## **5.1 Unique Document URI** 

Every document that is issued and made accessible via DigiLocker must have a unique way to resolve to the correct repository without conflict. This is critical to eliminate the need for all documents reference to be in one system. Federated repositories storing documents issued by various departments/agencies must be “reachable” via the gateway in a unique fashion. 

All documents issued in compliance to DLTS should have the following URI format: **`IssuerId-DocType-DocId`** where 

**`IssuerId`** is a unique issuer entity ID across the country **`DocType`** is the document type optionally defined by the issuer **`DocId`** is a unique document ID within the issuer system 

## **5.2 Issuer ID (mandatory)** 

All departments/agencies within government issuing citizen documents, termed as “ _Issuers_ ” must have a unique identification to ensure all documents issued by them are accessible via DLTS gateway. 

It is recommended that list of unique issuer codes be derived via their domain URL whenever available and be published as part of e-governance standard codification scheme with ability to add new issuers on need basis. When URL is not available for a department, a unique (alpha) code may be assigned. 

5 

Issuer API Specification 

Examples of issuer Ids are “maharashtra.gov.in” (Maharashtra State Government), “kseeb.kar.nic.in” (Karnataka School Board”, “cbse.nic.in” (CBSE School Board), “UDEL” (Delhi University), etc. These codes **MUST BE unique across India** and published as part of standard e-governance codification list. 

## **5.3 Document Type (mandatory)** 

Issuers can freely define a list of document types for their internal classification. For example, CBSE may classify certificates into “MSTN” (10th mark sheet), “KVPY” (certificate issued to KVPY scholarship fellows), etc. There are no requirements for publishing these via any central registry. 

Classifying documents into various types allows issuers to choose different repositories for different types. This is to future proof the design without making assumption that all certificates issued by the issuer are available in same repository. This also allows migration from one repository to another in a gradual way. Issuers are free to define their document types without worrying any collaboration across other issuers. Keeping the length minimal allows manual entry of document URI without making it too long. Hence it is recommended to keep length to be only up to 5. 

**It is recommended that issuers define document types either using pure alpha caseinsensitive strings of length up to 5. These document types MUST BE unique WITHIN the issuer system.** This classification within the issuer system also allows versioning of documents making future documents to be of different formats and in different repositories without having the need to have all documents in one repository. **If need arises in future to go beyond length 5, maximum length of doc type can easily use increased without breaking compatibility any existing systems and documents.** 

## **5.4 Document ID (mandatory)** 

A document ID determined by the department/agency (issuer) should be assigned to every document. It MUST BE unique either within the document types of that issuer or it can be unique across all document types of that issuer. 

**Document ID is an alpha-numeric string with maximum length of 10. It is recommended that issuers define document IDs either using pure alpha caseinsensitive string using a RANDOM number/string generator. Document IDs MUST BE unique WITHIN the issuer system within a document type. If need arises in future to go beyond length 10, maximum length of doc ID can easily use increased without breaking compatibility any existing systems and documents.** Using random string eliminates the possibility of “guessing” next sequence number and accessing a list of documents in a sequential way. This is critical to ensure security of documents and ensures document can be accessed ONLY IF the requester “knows” the actual document ID (instead of guessing sequential numbers). 

It is highly recommended that issuer needing to issue a total of _**n**_ documents within a document type use at least _**10n**_ random space from which the strings/numbers are chosen to randomly allocate. Notice that since document types allow further classification, it is suggested to keep the length **minimal** . Since issuers can easily add a new document type without any collaboration and approvals across other issuers, if more numbers are required, a new document type may be introduced. 

6 

Issuer API Specification 

## **6. Document Issuance Flow** 

Document issuance flow is given below: 

1. Create a digitally signed e-document complying to DLTS specification with a unique URI . 

   - a. Issuer entity uses the unique code for itself (obtain a new one if not already listed) that is available in common DLTS Issuer Codification e-governance standards. This is a country wide “Unique Issuer ID”. 

   - b. Document type codification is done by the Digital Locker system administrator. Issuers may choose an available document type or if a new type of document is being issued then request Digital Locker team to create the required document type. 

2. Issuer should create a document repository for storing documents and making it available online. This could be an existing database or document management system where the issued documents are stored. 

3. Issue the printed document to the individual(s) for whom the document is issued to with a human readable document URI. 

   - a. Issuer should also offer an option to people to push the document URI to the digital lockers of the resident for whom the document was issued. 

## **7. E-Document Specifications** 

## **7.1 Document URI** 

All documents issued in compliance to DLTS should have the following URI format: **`<IssuerId>[-DocType]-<DocId>`** 

Where, 

**`IssuerId`** (mandatory) - is a unique issuer entity ID. This is a unique pure alpha case-insensitive string. To easily make it unique, department’s domain URL can be used whenever available. The list of issuer Ids must be published and should have a mechanism to add new ones as required. **Unique list of Issuer IDs MUST BE unique and published via central e-governance codification scheme** . 

**`DocType`** (mandatory) - is the document type optionally defined by the issuer. This is highly recommended for document classification and versioning purposes. Issuers may decide their own classification mechanism. This is a 5 char pure alpha string which can be expanded in future as needed. 

**`DocId`** (mandatory) - is a unique document ID of length up to 10 within the issuer system. It is highly recommended that this is either purely numeric or alpha to avoid confusion with “0” with “o” etc. Also, it is highly recommended to use random strings to avoid guessing the sequence of document IDs. 

## **7.2 Document Owner** 

DigiLocker ensures that the individual can access the document from issuer’s repository only when the owner uniquely identifies a document that belong to him/her and the individual’s profile data matches with the document data in the issuer’s repository. This ensures that the documents are not misused. 

7 

Issuer API Specification 

## **7.3 Document Format** 

All e-documents must be represented in PDF or XML format complying to DLTS specifications. This ensures that a standardized XML structure is used to capture common attributes of all documents. 

## **8. Issuer APIs** 

The issuer organization integrating with Digital Locker maintains the documents/certificates in its own repository (database or file system). The issuer application provides APIs to Digital Locker to access the documents in this repository. Each issuer organization will have to implement 1 API to integrate with the Digital Locker system.  This  API is: 

1. Pull URI Request API:  This REST based pull API has to be implemented by the issuer organization to allow a locker owner to query the issuer repository by providing his/her Aadhaar number or any other identifier applicable to issuer organization (such as Roll number + Year + Class for CBSE mark sheet).  This way the issuer may provide the URI of the document that is linked to the Aadhaar number or other identifiers provided by the resident. 

This API is defined in greater details in subsequent sections. 

## **8.1 Pull URI Request API** 

The REST based Pull URI Request API has to be implemented by the issuers and will be consumed by Digital Locker application. This API will be invoked when a citizen searches the issuer repository for his/her certificate. If the certificate data is Aadhaar seeded, the issuer may choose to use Aadhaar number as the search parameter. Digital Locker provides Aadhaar number, name and date of birth as on Aadhaar to the issuer API as additional parameters. The option for these Aadhaar based parameters can be selected while configuring this API in Digital Locker Partner’s Portal. If the certificate data is not Aadhaar seeded then the issuer may use any other unique parameter e.g. driving license number to search for a driving license. These custom parameters will be passed in the UDF elements as shown in the sample request below. The custom parameter(s) can be configured while configuring the API in the DigiLocker Partner’s Portal. The Digital Locker system will query the issuer repository to fetch the URI for any document that match the search criteria. The citizen can save this URI in his/her Digital Locker. It is strongly recommended that the issuer API validate that the name, date of birth details sent by DigiLocker in Aadhaar parameters match with the corresponding details on the certificate before returning the certificate data. This will ensure that only authentic owners get access to a certificate. 

## **8.1.1 Pull URI Request Format** 

**HTTP Method:** POST 

## **HTTP Request Header Parameters:** 

- Content-Type: application/xml 

- x-digilocker-hmac: This is used for authentication and to verify the integrity of the request.  DigiLocker calculates the hash message authentication code (hmac) of the HTTP request body using SHA256 hashing algorithm and the API Key provided by the issuer as the hashing key. The API Key is specified by the issuer while configuring the Pull URI API in DigiLocker Partner Portal. The resulting hmac is converted to Base64 format and sent in this parameter. It is strongly recommended that the issuer API 

8 

Issuer API Specification 

calculates the hmac of the HTTP request body, convert it to Base64 and match it with this parameter to ensure authenticity of the request. 

The following is the XML request template for the PULL URI Request API. 

```
<?xml version="1.0"encoding="UTF-8"standalone="yes"?>
<PullURIRequest xmlns="http://tempuri.org/"ver="3.0"ts="YYYY-MM-
DDThh:mm:ss+/-nn:nn"txn="1234"orgId="" keyhash=""
format="xml/pdf/both">
 <DocDetails>
    <DocType></DocType> //Document type
    <DigiLockerId></DigiLockerId > //Unique 36 character DigiLocker Id
    <UID></UID> //MD5 Hash of Aadhaar Number (Optional)
    <FullName> </FullName> //Name as on Aadhaar (Optional)
    <DOB></DOB> //Date of birth as on Aadhaar (Optional)
    <Photo></Photo> //Base 64 encoded JPEG photograph as on Aadhaar
(Optional)
    <UDF1></UDF1> //User defined field
    <UDF2></UDF2> //User defined field
    <UDF3></UDF3> //User defined field
...
    <UDFn></UDFn> //User defined field
</DocDetails>
</PullURIRequest>
```

## **8.1.2 Pull URI Request Elements** 

Various elements/attributes in the request are described below- 

|**Sr.**<br>**No.**|**XML Element**|**Mandatory (M)/**<br>**Optional (O)**|**Description**|
|---|---|---|---|
|1.|ver|M|API version.|
|2.|ts|M|A timestamp value. This will be<br>used to verify the<br>keyHash<br>element described below.|
|3.|KeyHash|M|Sha256 hashing of defined API key<br>and timestamp.|
|4.|txn|M|Transaction id.|
|5.|orgId|M|Org Id is the user id provided to<br>the Digital Locker application by<br>the<br>issuer<br>application<br>for<br>accessing the API.|
|6.|format|M|Indicates the desired format of the<br>certificate data in the response.<br>Possible values of this attribute<br>are:<br>**xml**<br>**(default**<br>**value)**:<br>for<br>certificate<br>data<br>in<br>machine<br>readable xml format|



9 

## Issuer API Specification 

||||**both**: for certificate data in both<br>xml and pdf format. Please see the<br>response section below for more<br>details.|
|---|---|---|---|
|7.|DocType|M|Digital Locker will pass the<br>document type being searched in<br>this parameter.|
|8.|DigiLockerId|M|A unique 36 character DigiLocker<br>Id of the user account.|
|9.|UID|O|MD5 Hash of Aadhaar Number of<br>the DigiLocker user searching for<br>the document/certificate. This is<br>an optional parameter and will be<br>sent only if the issuer opts for it<br>while configuring the API on<br>Digital Locker Issuer Portal.|
|10.|FullName|O|Name of the DigiLocker user<br>searching<br>for<br>the<br>document/certificate<br>as<br>on<br>Aadhaar. This is an optional<br>parameter and will be sent only if<br>the issuer opts for it while<br>configuring the API on Digital<br>Locker Issuer Portal.|
|11.|DOB|O|Date of birth of the DigiLocker<br>user<br>searching<br>for<br>the<br>document/certificate<br>as<br>on<br>Aadhaar in DD-MM-YYYY format.<br>This is an optional parameter and<br>will be sent only if the issuer opts<br>for it while configuring the API on<br>Digital Locker Issuer Portal.|
|12.|Photo|O|The base 64 encoded contents of<br>JPEG photograph as on Aadhaar.<br>This is an optional parameter and<br>will be sent only if the issuer opts<br>for it while configuring the API on<br>Digital Locker Issuer Portal.|
|13.|UDF1…n|M|User defined search parameters<br>to<br>search<br>a<br>unique<br>document/certificate. The <UDF><br>may be <RollNo> for CBSE,<br><RegistrationNo><br>for<br>Transportation Dept. and <PAN><br>for Income Tax Dept. The search<br>parameters for the API will be<br>configured in the issuer portal of<br>Digital Locker while configuring<br>this API.|



10 

Issuer API Specification 

## **8.1.3 Pull URI Response Format** 

The response to the Pull URI request will include the URI of the document linked to the given search criteria in the request as well as the base 64 encoded data of the document.  The issuer will provide the response back to the Digital Locker system synchronously. 

The following is the XML response template for the Pull URI Response API. 

```
<?xml version="1.0"encoding="UTF-8"standalone="yes"?>
  <PullURIResponse xmlns:ns2="http://tempuri.org/">
    <ResponseStatus Status="1"ts="2016-01-11T14:44:48+05:30"
txn="1452503688">1</ResponseStatus>//1-Success //0-Failure //9-Pending
    <DocDetails>
        <IssuedTo>
          <Persons>
            <Person name="Sunil Kumar"dob="31-12-1990"
gender="Male/Female/Transgender"phone="9876543210">
              <Photo format=" PNG/JPG/JPEG">Base 64 encoded image
content</Photo>
            </Person>
            <Person name="SunitaDevi" dob="25-03-1993"
gender="Male/Female/Transgender" phone="9873451238"/>
          </Persons>
        </IssuedTo>
        <URI>in.gov.dept.state-INCER-1234567</URI>
        <DocContent>
//Base64 encoded string of PDF file
</DocContent>
        <DataContent>
//Base64 encoded certificate metadata in XML format
</DataContent>
    </DocDetails>
  </PullURIResponse>
```

## **8.1.4 Pull URI Response Elements** 

Various elements/attributes in the response are described below- 

|**Sr.**<br>**No.**|**XML Element**|**Mandatory (M)/**<br>**Optional (O)**|**Description**|
|---|---|---|---|
|1.|ts|M|A timestamp value as sent in the<br>request.|
|2.|txn|M|Transaction id value as sent in the<br>request.|
|3.|Status|M|1 for success, 0 for error and 9 for<br>pending.|



11 

## Issuer API Specification 

||||The issuer department may do a<br>manual verification of the Pull<br>Request and take a decision to<br>provide a document at a later<br>time. In this case the response<br>status should contain value 9.<br>DigiLocker<br>will<br>show<br>an<br>appropriate message to the user<br>in this case. Upon successful<br>verification,<br>the<br>issuer<br>department can use PUSH URI API<br>as mentioned in Digital Locker<br>Dedicated<br>Repository<br>API<br>Specification.|
|---|---|---|---|
|4.|DocDetails|M|Issuer can add meta content<br>specific to document here.|
|5.|IssuedTo|M|Contains the details about the<br>individual/s<br>to<br>whom<br>the<br>certificate is issued. It contains<br>one or more Person/s elements.|
|6.|Persons|M|Contains the details about the<br>individual/s<br>to<br>whom<br>the<br>certificate is issued. It contains<br>one or more Person/s elements. If<br>you select,_Match Name, DoB,_<br>_Gender or Mobile_option while<br>configuring Pull URI API in<br>DigiLocker<br>Partner’s<br>Portal,<br>DigiLocker<br>matches<br>the<br>corresponding details of each<br>individual in this list with the<br>name in DigiLocker KYC profile. If<br>the information of any one of the<br>individual matches, DigiLocker<br>will provide the certificate to the<br>individual.|
|7.|Person|M|Contains the details about an<br>individual to whom the certificate<br>is issued.|
|8.|name|M|The name of individual as on the<br>document as per the issuer’s<br>record. If you select,_Match Name_<br>option while configuring Pull URI<br>API in DigiLocker Partner’s Portal,<br>DigiLocker uses this name to<br>match<br>with<br>the<br>name<br>in<br>DigiLocker KYC profile.|
|9.|dob|M|The date of birth of individual as<br>on the document as per the<br>issuer’s record in DD-MM-YYYY|



12 

## Issuer API Specification 

||||format. If you select,_Match DoB_<br>option while configuring Pull URI<br>API in DigiLocker Partner’s Portal,<br>DigiLocker uses this field to match<br>with the DoB in DigiLocker KYC<br>profile.|
|---|---|---|---|
|10.|gender|M|The gender of individual as on the<br>document as per the issuer’s<br>record. If you select,_Match Gender_<br>option while configuring Pull URI<br>API in DigiLocker Partner’s Portal,<br>DigiLocker uses this field to match<br>with the Gender in DigiLocker<br>KYC profile. The possible values<br>for this field are Male, Female or<br>Other|
|11.|phone|M|The mobile number of individual<br>as on the document as per the<br>issuer’s record. If you select,<br>_Match_<br>_Mobile_<br>option<br>while<br>configuring Pull URI API in<br>DigiLocker<br>Partner’s<br>Portal,<br>DigiLocker uses this field to match<br>with the mobile number in<br>DigiLocker profile.|
|12.|Photo|O|Contains the base64 encoded<br>content of photograph in PNG, JPG<br>or JPEG format of the individual to<br>whom the certificate is issued.|
|13.|format|M|Format of the photograph. It will<br>contain one of the following<br>values:<br>PNG<br>JPG<br>JPEG|
|14.|URI|M|URI corresponding to the search<br>criteria<br>that<br>identifies<br>the<br>document uniquely.|
|15.|DocContent|M|Enclose the Base64 byte encoded<br>contents of PDF file in this<br>element. The DocContent element<br>should be sent only if the_format_<br>attribute in the original request is<br>sent as“pdf”or“both”.|
|16.|DataContent|M|Enclose the base64 byte encoded<br>certificate<br>metadata<br>in<br>XML<br>format.|



**8.1.5 Configuration of Pull URI API in DigiLocker Partner Portal** 

Once you have developed and deployed the API on your server, the next step is to provide the details of this API to DigiLocker so that DigiLocker can call the API. For this, login in to 

13 

Issuer API Specification 

DigiLocker Partner Portal (https://apisetu.gov.in/) using your issuer credentials. On the left menu in your account click on DigiLocker APIs->Pull URI Request API. You will see an ‘Add’ button on the page displayed on the right side. Click on the ‘Add’ button to add a new API. Configure the details of your API in the page displayed and click ‘Submit’. You can also add the details of the user defined parameters (UDFs) if you are using custom parameters to search a document. 

With this step, DigiLocker now knows about the end point of your API along with the parameter it takes. DigiLocker uses these configuration details to display the search document screen to a user. Please see the image above for more details. 

14 

