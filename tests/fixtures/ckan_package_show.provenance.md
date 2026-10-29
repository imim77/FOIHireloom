The fixture is a projection of the public response observed on 2026-10-29:

https://data.gov.hr/ckan/api/3/action/package_show?id=slobodna-radna-mjesta-po-zupanijama-u-rh-i-eu

It keeps only the dataset name and resource ID, name, description, URL, format
and state. At observation time there were 21 Croatian county resources and
one EU resource. County labels were in `description`; `name` was absent/null.
The resource URLs are metadata, not evidence that the RSS endpoints are reachable.

CKAN's response envelope is documented at https://docs.ckan.org/en/latest/api/.
Error responses in the tests are controlled examples of the documented envelope
or HTTP/transport failures; they are not recordings of provider outages.
