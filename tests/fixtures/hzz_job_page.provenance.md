The job page fixtures come from public HZZ detail pages observed on 2026-10-30:

- `hzz_job_page_school.html`: https://burzarada.hzz.hr/RadnoMjesto_Ispis.aspx?WebSifra=167879154
- `hzz_job_page_restaurant.html`: https://burzarada.hzz.hr/RadnoMjesto_Ispis.aspx?WebSifra=167822489
- `hzz_job_page_error.html`: the page HZZ redirected to for an invalid WebSifra
  (https://burzarada.hzz.hr/ErrorPage.aspx?errorCode=GenericError), returned with HTTP 200

The `ctl00_MainContent_pnlAjaxBlock` block of each job page is copied as served,
including element IDs, whitespace, entities and the list markup HZZ uses when a
field has several values. We removed the site navigation, scripts and styles
around that block. Two parts are edited:

- The free-text "Ostale informacije" was shortened. It keeps the original
  markup patterns: `<p>`, `<strong>`, `<br />`, `<ul>` and `&nbsp;`.
- The employer contact section was replaced, because it held a person's name,
  phone numbers and e-mail address.

The school page covers a multi-value "Vrsta zaposlenja" list, the optional
"Način rada" field and a date without a leading zero ("6.11.2026."). The
restaurant page covers a multi-value "Razina obrazovanja" list. The error page
is reduced to its notice.
