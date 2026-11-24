Gurugram district boundary
====

`gurugram_boundary.geojson` is the administrative boundary of Gurugram district, Haryana (OpenStreetMap relation 3577685),
fetched on 2026-11-25 through the OpenStreetMap Nominatim geocoder.

* Source: https://www.openstreetmap.org/relation/3577685
* License: Open Database License 1.0, (c) OpenStreetMap contributors (https://www.openstreetmap.org/copyright)

It is a community-published reference, not a legal boundary. It is used only to decide which one-kilometre grid squares belong to
Gurugram (`GG43_*` cells in `areas.sqlite`); Delhi's cells use `delhi_boundary.geojson` (DataMeet, CC BY-SA 2.5 India).
The district was chosen over the smaller municipal polygon (relation 10398244) because it covers 99% of the Gurugram buildings
in the property map, against 79% for the municipal one, which leaves out Sohna.
