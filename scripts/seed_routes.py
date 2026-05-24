from decimal import Decimal
import sys
import traceback
import uuid
from datetime import datetime

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.stop import Stop
from app.models.route import Route
from app.models.route_stop import RouteStop
from app.models.enums import RouteStatus


ROUTES = [
    {"route_code":"001","route_name":"Megenagna → Kara","price":"1.4","distance_km":7.7,"stops":[{"sequence":1,"name":"Megenagna","latitude":9.0192,"longitude":38.8021},{"sequence":2,"name":"Gurd Shola","latitude":9.0208,"longitude":38.8127},{"sequence":3,"name":"Kara","latitude":9.0094,"longitude":38.8127}]},
    {"route_code":"002","route_name":"Kore Mekanisa → Merkato","price":"2.0","distance_km":11.1,"stops":[{"sequence":1,"name":"Kore Mekanisa","latitude":9.015,"longitude":38.725},{"sequence":2,"name":"Lideta","latitude":9.0283,"longitude":38.7413},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"003","route_name":"Ayertena → Minilik Square","price":"2.0","distance_km":10.8,"stops":[{"sequence":1,"name":"Ayertena","latitude":9.0703,"longitude":38.7449},{"sequence":2,"name":"Mexico","latitude":9.0258,"longitude":38.7538},{"sequence":3,"name":"Minilik Square","latitude":9.0441,"longitude":38.748}]},
    {"route_code":"004","route_name":"Kaliti → Merkato","price":"3.25","distance_km":19.4,"stops":[{"sequence":1,"name":"Kaliti","latitude":8.9513,"longitude":38.7799},{"sequence":2,"name":"Kira","latitude":9.0,"longitude":38.78},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"005","route_name":"Kore Mekanisa → Minilik Square","price":"2.4","distance_km":12.7,"stops":[{"sequence":1,"name":"Kore Mekanisa","latitude":9.015,"longitude":38.725},{"sequence":2,"name":"Bisrategebreil","latitude":9.02,"longitude":38.734},{"sequence":3,"name":"Minilik Square","latitude":9.0441,"longitude":38.748}]},
    {"route_code":"006","route_name":"Kera → Semen Addisu Gebeya","price":"2.0","distance_km":9.9,"stops":[{"sequence":1,"name":"Kera","latitude":9.0022,"longitude":38.7538},{"sequence":2,"name":"Shebel","latitude":9.02,"longitude":38.748},{"sequence":3,"name":"Semen Addisu Gebeya","latitude":9.05,"longitude":38.74}]},
    {"route_code":"007","route_name":"Megenagna → Aleltu","price":"10.0","distance_km":49.0,"stops":[{"sequence":1,"name":"Megenagna","latitude":9.0192,"longitude":38.8021},{"sequence":2,"name":"Kotebe","latitude":9.0611,"longitude":38.8295},{"sequence":3,"name":"Aleltu","latitude":None,"longitude":None}]},
    {"route_code":"008","route_name":"Kechene → Merkato","price":"1.4","distance_km":9.4,"stops":[{"sequence":1,"name":"Kechene","latitude":9.053,"longitude":38.785},{"sequence":2,"name":"Yohannes","latitude":9.042,"longitude":38.75},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"009","route_name":"Birass Cilinic Bole School → Piazza","price":"2.0","distance_km":10.5,"stops":[{"sequence":1,"name":"Birass Cilinic Bole School","latitude":9.005,"longitude":38.787},{"sequence":2,"name":"Kasanchiz","latitude":9.01,"longitude":38.7767},{"sequence":3,"name":"Piazza","latitude":9.0396,"longitude":38.7513}]},
    {"route_code":"010","route_name":"Kotebe Teachers Collage → Piazza","price":"2.4","distance_km":12.7,"stops":[{"sequence":1,"name":"Kotebe Teachers Collage","latitude":9.0611,"longitude":38.8295},{"sequence":2,"name":"Kebena","latitude":9.0367,"longitude":38.7767},{"sequence":3,"name":"Piazza","latitude":9.0396,"longitude":38.7513}]},
    {"route_code":"011","route_name":"Kolfe → Minilik Hospital","price":"2.0","distance_km":10.0,"stops":[{"sequence":1,"name":"Kolfe","latitude":9.0394,"longitude":38.7159},{"sequence":2,"name":"Atkilt Tera","latitude":9.038,"longitude":38.72},{"sequence":3,"name":"Minilik Hospital","latitude":9.0484,"longitude":38.7492}]},
    {"route_code":"012","route_name":"Gurara → Merkato","price":"2.0","distance_km":9.9,"stops":[{"sequence":1,"name":"Gurara","latitude":9.056,"longitude":38.772},{"sequence":2,"name":"Afncho Ber","latitude":9.038,"longitude":38.749},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"013","route_name":"Italy Embassy → Merkato","price":"2.0","distance_km":9.9,"stops":[{"sequence":1,"name":"Italy Embassy","latitude":9.022,"longitude":38.763},{"sequence":2,"name":"Cinema Ethiopia","latitude":None,"longitude":None},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"014","route_name":"Saris Abo → Minilik Square","price":"2.4","distance_km":12.3,"stops":[{"sequence":1,"name":"Saris Abo","latitude":8.9748,"longitude":38.7925},{"sequence":2,"name":"Gandi Hospital","latitude":9.0254,"longitude":38.7549},{"sequence":3,"name":"Minilik Square","latitude":9.0441,"longitude":38.748}]},
    {"route_code":"015","route_name":"Megenagna → Merkato","price":"2.0","distance_km":10.5,"stops":[{"sequence":1,"name":"Megenagna","latitude":9.0192,"longitude":38.8021},{"sequence":2,"name":"Abuare","latitude":9.025,"longitude":38.77},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"016","route_name":"Kidanemihret → Merkato","price":"1.4","distance_km":7.9,"stops":[{"sequence":1,"name":"Kidanemihret","latitude":9.06,"longitude":38.75},{"sequence":2,"name":"Afncho Ber","latitude":9.038,"longitude":38.749},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"017","route_name":"Kusquam → Merkato","price":"2.0","distance_km":9.1,"stops":[{"sequence":1,"name":"Kusquam","latitude":9.07,"longitude":38.754},{"sequence":2,"name":"Kidste Mariam","latitude":9.065,"longitude":38.751},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"018","route_name":"Keraniyo → Merkato","price":"1.4","distance_km":7.3,"stops":[{"sequence":1,"name":"Keraniyo","latitude":9.045,"longitude":38.72},{"sequence":2,"name":"Kolfe Dildy","latitude":9.043,"longitude":38.718},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"019","route_name":"Asko → Piazza","price":"2.0","distance_km":12.3,"stops":[{"sequence":1,"name":"Asko","latitude":9.063,"longitude":38.71},{"sequence":2,"name":"Pawlos","latitude":9.051,"longitude":38.731},{"sequence":3,"name":"Piazza","latitude":9.0396,"longitude":38.7513}]},
    {"route_code":"020","route_name":"Dile Ber → Merkato","price":"1.4","distance_km":8.6,"stops":[{"sequence":1,"name":"Dile Ber","latitude":9.048,"longitude":38.712},{"sequence":2,"name":"Enkulal Fabrica","latitude":9.046,"longitude":38.715},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"021","route_name":"Fildoro → Merkato","price":"1.4","distance_km":8.6,"stops":[{"sequence":1,"name":"Fildoro","latitude":9.05,"longitude":38.708},{"sequence":2,"name":"Kolfe Dildy","latitude":9.043,"longitude":38.718},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"022","route_name":"Summit Condominium → Legehar","price":"2.4","distance_km":12.3,"stops":[{"sequence":1,"name":"Summit Condominium","latitude":9.029,"longitude":38.845},{"sequence":2,"name":"22 Mazoria","latitude":9.0308,"longitude":38.8059},{"sequence":3,"name":"Legehar","latitude":9.0164,"longitude":38.7588}]},
    {"route_code":"023","route_name":"Lamberet → Merkato","price":"2.4","distance_km":12.4,"stops":[{"sequence":1,"name":"Lamberet","latitude":9.035,"longitude":38.86},{"sequence":2,"name":"Afncho Ber","latitude":9.038,"longitude":38.749},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"024","route_name":"Dire Sololia → Merkato","price":"2.7","distance_km":15.9,"stops":[{"sequence":1,"name":"Dire Sololia","latitude":9.08,"longitude":38.68},{"sequence":2,"name":"Pawlos","latitude":9.051,"longitude":38.731},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"025","route_name":"Legehar → Akaki","price":"3.25","distance_km":19.0,"stops":[{"sequence":1,"name":"Legehar","latitude":9.0164,"longitude":38.7588},{"sequence":2,"name":"Gotera","latitude":8.9863,"longitude":38.7517},{"sequence":3,"name":"Akaki","latitude":8.8798,"longitude":38.7994}]},
    {"route_code":"026","route_name":"Merkato → Sebeta","price":"4.5","distance_km":25.5,"stops":[{"sequence":1,"name":"Merkato","latitude":9.0364,"longitude":38.7469},{"sequence":2,"name":"Coca Cola","latitude":8.99,"longitude":38.735},{"sequence":3,"name":"Sebeta","latitude":8.9138,"longitude":38.626}]},
    {"route_code":"027","route_name":"Legehar → Kaliti","price":"2.4","distance_km":14.9,"stops":[{"sequence":1,"name":"Legehar","latitude":9.0164,"longitude":38.7588},{"sequence":2,"name":"Gotera","latitude":8.9863,"longitude":38.7517},{"sequence":3,"name":"Kaliti","latitude":8.9513,"longitude":38.7799}]},
    {"route_code":"028","route_name":"Asko Sansuzi → Merkato","price":"2.0","distance_km":11.1,"stops":[{"sequence":1,"name":"Asko Sansuzi","latitude":9.068,"longitude":38.705},{"sequence":2,"name":"Mesalemia","latitude":9.056,"longitude":38.718},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"029","route_name":"Addisu Sefer → Merkato","price":"2.4","distance_km":12.7,"stops":[{"sequence":1,"name":"Addisu Sefer","latitude":9.056,"longitude":38.72},{"sequence":2,"name":"Teklehaimanot","latitude":9.0364,"longitude":38.753},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"030","route_name":"Sululta → Merkato","price":"4.5","distance_km":25.5,"stops":[{"sequence":1,"name":"Sululta","latitude":9.181,"longitude":38.778},{"sequence":2,"name":"Semen Gebeya","latitude":9.05,"longitude":38.74},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"031","route_name":"Legehar → Shiromeda","price":"1.4","distance_km":7.4,"stops":[{"sequence":1,"name":"Legehar","latitude":9.0164,"longitude":38.7588},{"sequence":2,"name":"4 Kilo","latitude":9.0436,"longitude":38.7628},{"sequence":3,"name":"Shiromeda","latitude":9.0669,"longitude":38.7633}]},
    {"route_code":"032","route_name":"Hana Mariam Kotebe → Legehar","price":"2.0","distance_km":10.6,"stops":[{"sequence":1,"name":"Hana Mariam","latitude":9.062,"longitude":38.83},{"sequence":2,"name":"22 Mazoria","latitude":9.0308,"longitude":38.8059},{"sequence":3,"name":"Legehar","latitude":9.0164,"longitude":38.7588}]},
    {"route_code":"033","route_name":"Kotebe Gebriel → 4 Kilo","price":"2.0","distance_km":11.4,"stops":[{"sequence":1,"name":"Kotebe","latitude":9.0611,"longitude":38.8295},{"sequence":2,"name":"Kebena","latitude":9.0367,"longitude":38.7767},{"sequence":3,"name":"4 Kilo","latitude":9.0436,"longitude":38.7628}]},
    {"route_code":"034","route_name":"German Square → Merkato","price":"2.0","distance_km":9.8,"stops":[{"sequence":1,"name":"German Square","latitude":9.01,"longitude":38.762},{"sequence":2,"name":"Kera","latitude":9.0022,"longitude":38.7538},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"035","route_name":"Lebu Musica Bet → Merkato","price":"2.4","distance_km":15.0,"stops":[{"sequence":1,"name":"Lebu Musica Bet","latitude":8.97,"longitude":38.72},{"sequence":2,"name":"Lafto","latitude":8.9836,"longitude":38.7363},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"036","route_name":"Kara Kore → Legehar","price":"2.0","distance_km":11.7,"stops":[{"sequence":1,"name":"Kara Kore","latitude":9.005,"longitude":38.82},{"sequence":2,"name":"Torhailoch","latitude":8.9663,"longitude":38.7444},{"sequence":3,"name":"Legehar","latitude":9.0164,"longitude":38.7588}]},
    {"route_code":"037","route_name":"Keraniyo → Minilik Square","price":"2.0","distance_km":12.0,"stops":[{"sequence":1,"name":"Keraniyo","latitude":9.045,"longitude":38.72},{"sequence":2,"name":"Mexico","latitude":9.0258,"longitude":38.7538},{"sequence":3,"name":"Minilik Square","latitude":9.0441,"longitude":38.748}]},
    {"route_code":"038","route_name":"Lebu Musica Bet → 6 Kilo","price":"2.0","distance_km":11.0,"stops":[{"sequence":1,"name":"Lebu Musica Bet","latitude":8.97,"longitude":38.72},{"sequence":2,"name":"Minilik Square","latitude":9.0441,"longitude":38.748},{"sequence":3,"name":"6 Kilo","latitude":9.053,"longitude":38.7698}]},
    {"route_code":"039","route_name":"Bole School Medhanialem → Merkato","price":"2.0","distance_km":9.6,"stops":[{"sequence":1,"name":"Bole School Medhanialem","latitude":9.005,"longitude":38.787},{"sequence":2,"name":"Kasanchiz","latitude":9.01,"longitude":38.7767},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"040","route_name":"Kara Alo → Merkato","price":"2.7","distance_km":17.9,"stops":[{"sequence":1,"name":"Kara Alo","latitude":8.99,"longitude":38.83},{"sequence":2,"name":"4 Kilo","latitude":9.0436,"longitude":38.7628},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"041","route_name":"Eyesus Church → Merkato","price":"1.4","distance_km":8.5,"stops":[{"sequence":1,"name":"Eyesus Church","latitude":9.038,"longitude":38.761},{"sequence":2,"name":"4 Kilo","latitude":9.0436,"longitude":38.7628},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"042","route_name":"Megenagna → Bole Legehar","price":"2.0","distance_km":9.8,"stops":[{"sequence":1,"name":"Megenagna","latitude":9.0192,"longitude":38.8021},{"sequence":2,"name":"Bole","latitude":8.9981,"longitude":38.799},{"sequence":3,"name":"Bole Legehar","latitude":9.005,"longitude":38.79}]},
    {"route_code":"043","route_name":"Mekenesha → Merkato","price":"4.5","distance_km":30.2,"stops":[{"sequence":1,"name":"Mekenesha","latitude":9.3,"longitude":38.55},{"sequence":2,"name":"Mesalemia","latitude":9.056,"longitude":38.718},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"044","route_name":"Legedadi → Merkato","price":"4.5","distance_km":30.4,"stops":[{"sequence":1,"name":"Legedadi","latitude":9.1086,"longitude":38.9461},{"sequence":2,"name":"4 Kilo","latitude":9.0436,"longitude":38.7628},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"045","route_name":"Legehar → Dilbere","price":"1.4","distance_km":8.6,"stops":[{"sequence":1,"name":"Legehar","latitude":9.0164,"longitude":38.7588},{"sequence":2,"name":"Piazza","latitude":9.0396,"longitude":38.7513},{"sequence":3,"name":"Dilbere","latitude":9.08,"longitude":38.74}]},
    {"route_code":"046","route_name":"Gerji → 4 Kilo","price":"2.0","distance_km":11.2,"stops":[{"sequence":1,"name":"Gerji","latitude":9.0088,"longitude":38.8199},{"sequence":2,"name":"22 Mazoria","latitude":9.0308,"longitude":38.8059},{"sequence":3,"name":"4 Kilo","latitude":9.0436,"longitude":38.7628}]},
    {"route_code":"047","route_name":"Yenegew Fire School → Merkato","price":"1.4","distance_km":6.0,"stops":[{"sequence":1,"name":"Yenegew Fire School","latitude":9.035,"longitude":38.752},{"sequence":2,"name":"Michael","latitude":9.035,"longitude":38.752},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"048","route_name":"Bole Mikhael Square → Minilik Square","price":"2.0","distance_km":10.9,"stops":[{"sequence":1,"name":"Bole Michael","latitude":9.012,"longitude":38.796},{"sequence":2,"name":"Gandi Hospital","latitude":9.0254,"longitude":38.7549},{"sequence":3,"name":"Minilik Square","latitude":9.0441,"longitude":38.748}]},
    {"route_code":"049","route_name":"Ayat Condominium → Megenagna","price":"2.0","distance_km":8.8,"stops":[{"sequence":1,"name":"Ayat Condominium","latitude":9.0367,"longitude":38.8503},{"sequence":2,"name":"CMC","latitude":9.044,"longitude":38.8293},{"sequence":3,"name":"Megenagna","latitude":9.0192,"longitude":38.8021}]},
    {"route_code":"050","route_name":"Ayertena → Megenagna","price":"2.4","distance_km":12.1,"stops":[{"sequence":1,"name":"Ayertena","latitude":9.0703,"longitude":38.7449},{"sequence":2,"name":"Torhailoch","latitude":8.9663,"longitude":38.7444},{"sequence":3,"name":"Megenagna","latitude":9.0192,"longitude":38.8021}]},
    {"route_code":"051","route_name":"Betel Hospital → Merkato","price":"2.0","distance_km":10.9,"stops":[{"sequence":1,"name":"Betel Hospital","latitude":9.0075,"longitude":38.7392},{"sequence":2,"name":"Zenbwork","latitude":9.012,"longitude":38.755},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"052","route_name":"Gerji → Merkato","price":"2.4","distance_km":14.1,"stops":[{"sequence":1,"name":"Gerji","latitude":9.0088,"longitude":38.8199},{"sequence":2,"name":"Bole","latitude":8.9981,"longitude":38.799},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"053","route_name":"Bole Michael → Shiromeda","price":"2.0","distance_km":11.5,"stops":[{"sequence":1,"name":"Bole Michael","latitude":9.012,"longitude":38.796},{"sequence":2,"name":"Meskel Square","latitude":9.0142,"longitude":38.7637},{"sequence":3,"name":"Shiromeda","latitude":9.0669,"longitude":38.7633}]},
    {"route_code":"054","route_name":"Lafto → Legehar","price":"2.0","distance_km":9.5,"stops":[{"sequence":1,"name":"Lafto","latitude":8.9836,"longitude":38.7363},{"sequence":2,"name":"Kera","latitude":9.0022,"longitude":38.7538},{"sequence":3,"name":"Legehar","latitude":9.0164,"longitude":38.7588}]},
    {"route_code":"055","route_name":"Legehar → Gurara","price":"2.0","distance_km":9.5,"stops":[{"sequence":1,"name":"Legehar","latitude":9.0164,"longitude":38.7588},{"sequence":2,"name":"4 Kilo","latitude":9.0436,"longitude":38.7628},{"sequence":3,"name":"Gurara","latitude":9.056,"longitude":38.772}]},
    {"route_code":"056","route_name":"Saris Abo → Shiromeda","price":"2.4","distance_km":14.2,"stops":[{"sequence":1,"name":"Saris Abo","latitude":8.9748,"longitude":38.7925},{"sequence":2,"name":"Meskel Square","latitude":9.0142,"longitude":38.7637},{"sequence":3,"name":"Shiromeda","latitude":9.0669,"longitude":38.7633}]},
    {"route_code":"057","route_name":"Kara → Legehar","price":"2.4","distance_km":14.4,"stops":[{"sequence":1,"name":"Kara","latitude":9.0094,"longitude":38.8127},{"sequence":2,"name":"22 Mazoria","latitude":9.0308,"longitude":38.8059},{"sequence":3,"name":"Legehar","latitude":9.0164,"longitude":38.7588}]},
    {"route_code":"058","route_name":"Alem Bank → Legehar","price":"2.0","distance_km":12.0,"stops":[{"sequence":1,"name":"Alem Bank","latitude":8.964,"longitude":38.756},{"sequence":2,"name":"Torhailoch","latitude":8.9663,"longitude":38.7444},{"sequence":3,"name":"Legehar","latitude":9.0164,"longitude":38.7588}]},
    {"route_code":"059","route_name":"Betel Hospital → Minilik Square","price":"2.0","distance_km":11.5,"stops":[{"sequence":1,"name":"Betel Hospital","latitude":9.0075,"longitude":38.7392},{"sequence":2,"name":"Coca Cola","latitude":8.99,"longitude":38.735},{"sequence":3,"name":"Minilik Square","latitude":9.0441,"longitude":38.748}]},
    {"route_code":"060","route_name":"Debre Zeit → Legehar","price":"7.5","distance_km":47.2,"stops":[{"sequence":1,"name":"Debre Zeit","latitude":8.728,"longitude":38.9958},{"sequence":2,"name":"Gotera","latitude":8.9863,"longitude":38.7517},{"sequence":3,"name":"Legehar","latitude":9.0164,"longitude":38.7588}]},
    {"route_code":"061","route_name":"Ayat Condominium → Legehar","price":"2.7","distance_km":15.8,"stops":[{"sequence":1,"name":"Ayat Condominium","latitude":9.0367,"longitude":38.8503},{"sequence":2,"name":"22 Mazoria","latitude":9.0308,"longitude":38.8059},{"sequence":3,"name":"Legehar","latitude":9.0164,"longitude":38.7588}]},
    {"route_code":"062","route_name":"Sebeta → Legehar","price":"3.75","distance_km":23.8,"stops":[{"sequence":1,"name":"Sebeta","latitude":8.9138,"longitude":38.626},{"sequence":2,"name":"Torhailoch","latitude":8.9663,"longitude":38.7444},{"sequence":3,"name":"Legehar","latitude":9.0164,"longitude":38.7588}]},
    {"route_code":"063","route_name":"Merkato → Mekililand Birchko","price":"2.0","distance_km":9.1,"stops":[{"sequence":1,"name":"Merkato","latitude":9.0364,"longitude":38.7469},{"sequence":2,"name":"Atena Tera","latitude":9.038,"longitude":38.747},{"sequence":3,"name":"Mekililand Birchko","latitude":9.058,"longitude":38.72}]},
    {"route_code":"064","route_name":"6 Kilo → Megenagna","price":"2.0","distance_km":9.5,"stops":[{"sequence":1,"name":"6 Kilo","latitude":9.053,"longitude":38.7698},{"sequence":2,"name":"Kasanchiz","latitude":9.01,"longitude":38.7767},{"sequence":3,"name":"Megenagna","latitude":9.0192,"longitude":38.8021}]},
    {"route_code":"065","route_name":"Merkato → Alem Bank","price":"2.0","distance_km":11.0,"stops":[{"sequence":1,"name":"Merkato","latitude":9.0364,"longitude":38.7469},{"sequence":2,"name":"Coca Cola","latitude":8.99,"longitude":38.735},{"sequence":3,"name":"Alem Bank","latitude":8.964,"longitude":38.756}]},
    {"route_code":"066","route_name":"Merkato → Kara Kore","price":"2.0","distance_km":10.5,"stops":[{"sequence":1,"name":"Merkato","latitude":9.0364,"longitude":38.7469},{"sequence":2,"name":"Coca Cola","latitude":8.99,"longitude":38.735},{"sequence":3,"name":"Kara Kore","latitude":9.005,"longitude":38.82}]},
    {"route_code":"067","route_name":"Mekanisa Jemo → Legehar","price":"2.0","distance_km":10.2,"stops":[{"sequence":1,"name":"Jemo","latitude":8.9936,"longitude":38.7282},{"sequence":2,"name":"Mexico","latitude":9.0258,"longitude":38.7538},{"sequence":3,"name":"Legehar","latitude":9.0164,"longitude":38.7588}]},
    {"route_code":"068","route_name":"Torhailoch → Minilik Hospital","price":"2.0","distance_km":10.2,"stops":[{"sequence":1,"name":"Torhailoch","latitude":8.9663,"longitude":38.7444},{"sequence":2,"name":"Gibi Gebriel","latitude":8.978,"longitude":38.743},{"sequence":3,"name":"Minilik Hospital","latitude":9.0484,"longitude":38.7492}]},
    {"route_code":"069","route_name":"Philpos Church → Merkato","price":"1.4","distance_km":5.9,"stops":[{"sequence":1,"name":"Philpos Church","latitude":9.03,"longitude":38.745},{"sequence":2,"name":"Mesalemia","latitude":9.056,"longitude":38.718},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"070","route_name":"Kasanchis → Ayertena","price":"2.0","distance_km":11.0,"stops":[{"sequence":1,"name":"Kasanchiz","latitude":9.01,"longitude":38.7767},{"sequence":2,"name":"Mexico","latitude":9.0258,"longitude":38.7538},{"sequence":3,"name":"Ayertena","latitude":9.0703,"longitude":38.7449}]},
    {"route_code":"071","route_name":"Gerji → Balcha Hospital","price":"2.0","distance_km":11.0,"stops":[{"sequence":1,"name":"Gerji","latitude":9.0088,"longitude":38.8199},{"sequence":2,"name":"Bole Tenatabia","latitude":8.992,"longitude":38.81},{"sequence":3,"name":"Balcha Hospital","latitude":9.0333,"longitude":38.7558}]},
    {"route_code":"072","route_name":"Hana Mariam → Saris Abo","price":"1.0","distance_km":3.8,"stops":[{"sequence":1,"name":"Hana Mariam","latitude":9.062,"longitude":38.83},{"sequence":2,"name":"58 Kebele","latitude":9.058,"longitude":38.825},{"sequence":3,"name":"Saris Abo","latitude":8.9748,"longitude":38.7925}]},
    {"route_code":"073","route_name":"Legehar → Wingate School","price":"2.0","distance_km":10.2,"stops":[{"sequence":1,"name":"Legehar","latitude":9.0164,"longitude":38.7588},{"sequence":2,"name":"Torhailoch","latitude":8.9663,"longitude":38.7444},{"sequence":3,"name":"Wingate School","latitude":8.975,"longitude":38.756}]},
    {"route_code":"074","route_name":"CMC Michael → Merkato","price":"2.4","distance_km":13.3,"stops":[{"sequence":1,"name":"CMC","latitude":9.044,"longitude":38.8293},{"sequence":2,"name":"Tikur Anbessa","latitude":9.0476,"longitude":38.7628},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"075","route_name":"6 Kilo → Kera","price":"2.0","distance_km":10.4,"stops":[{"sequence":1,"name":"6 Kilo","latitude":9.053,"longitude":38.7698},{"sequence":2,"name":"Kasanchiz","latitude":9.01,"longitude":38.7767},{"sequence":3,"name":"Kera","latitude":9.0022,"longitude":38.7538}]},
    {"route_code":"076","route_name":"Megenagna → Kaliti","price":"2.7","distance_km":18.4,"stops":[{"sequence":1,"name":"Megenagna","latitude":9.0192,"longitude":38.8021},{"sequence":2,"name":"Zerihun Building","latitude":9.035,"longitude":38.815},{"sequence":3,"name":"Kaliti","latitude":8.9513,"longitude":38.7799}]},
    {"route_code":"077","route_name":"Ayertena → Kera","price":"1.0","distance_km":13.0,"stops":[{"sequence":1,"name":"Ayertena","latitude":9.0703,"longitude":38.7449},{"sequence":2,"name":"Sar Bet","latitude":9.0253,"longitude":38.7451},{"sequence":3,"name":"Kera","latitude":9.0022,"longitude":38.7538}]},
    {"route_code":"078","route_name":"Megenagna → Gofa Condominium","price":"2.4","distance_km":12.4,"stops":[{"sequence":1,"name":"Megenagna","latitude":9.0192,"longitude":38.8021},{"sequence":2,"name":"Bherawi","latitude":9.007,"longitude":38.766},{"sequence":3,"name":"Gofa Condominium","latitude":8.995,"longitude":38.755}]},
    {"route_code":"079","route_name":"4 Kilo → Summit","price":"2.4","distance_km":12.7,"stops":[{"sequence":1,"name":"4 Kilo","latitude":9.0436,"longitude":38.7628},{"sequence":2,"name":"Signal","latitude":9.048,"longitude":38.802},{"sequence":3,"name":"Summit Condominium","latitude":9.029,"longitude":38.845}]},
    {"route_code":"080","route_name":"Semen Gebeya → Megenagna","price":"2.4","distance_km":12.4,"stops":[{"sequence":1,"name":"Semen Gebeya","latitude":9.05,"longitude":38.74},{"sequence":2,"name":"Kasanchiz","latitude":9.01,"longitude":38.7767},{"sequence":3,"name":"Megenagna","latitude":9.0192,"longitude":38.8021}]},
    {"route_code":"081","route_name":"6 Kilo → Asko","price":"2.4","distance_km":13.0,"stops":[{"sequence":1,"name":"6 Kilo","latitude":9.053,"longitude":38.7698},{"sequence":2,"name":"Yohannes","latitude":9.042,"longitude":38.75},{"sequence":3,"name":"Asko","latitude":9.063,"longitude":38.71}]},
    {"route_code":"082","route_name":"Sefera Goro → Balcha Hospital","price":"2.4","distance_km":14.6,"stops":[{"sequence":1,"name":"Sefera Goro","latitude":9.015,"longitude":38.81},{"sequence":2,"name":"24 Kebele","latitude":9.015,"longitude":38.81},{"sequence":3,"name":"Balcha Hospital","latitude":9.0333,"longitude":38.7558}]},
    {"route_code":"083","route_name":"Ayat Condominium → 6 Kilo","price":"2.7","distance_km":18.0,"stops":[{"sequence":1,"name":"Ayat Condominium","latitude":9.0367,"longitude":38.8503},{"sequence":2,"name":"Kebena","latitude":9.0367,"longitude":38.7767},{"sequence":3,"name":"6 Kilo","latitude":9.053,"longitude":38.7698}]},
    {"route_code":"084","route_name":"Kolfe → Legehar","price":"2.0","distance_km":9.5,"stops":[{"sequence":1,"name":"Kolfe","latitude":9.0394,"longitude":38.7159},{"sequence":2,"name":"Amanuel","latitude":9.035,"longitude":38.738},{"sequence":3,"name":"Legehar","latitude":9.0164,"longitude":38.7588}]},
    {"route_code":"085","route_name":"Merkato → Holeta","price":"7.5","distance_km":45.0,"stops":[{"sequence":1,"name":"Merkato","latitude":9.0364,"longitude":38.7469},{"sequence":2,"name":"18 Mazoria","latitude":9.045,"longitude":38.74},{"sequence":3,"name":"Holeta","latitude":9.0553,"longitude":38.5041}]},
    {"route_code":"086","route_name":"Ayertena → Korki Fabrica","price":"2.4","distance_km":12.3,"stops":[{"sequence":1,"name":"Ayertena","latitude":9.0703,"longitude":38.7449},{"sequence":2,"name":"Mebrat Hail","latitude":9.0614,"longitude":38.7347},{"sequence":3,"name":"Korki Fabrica","latitude":9.075,"longitude":38.735}]},
    {"route_code":"087","route_name":"Wingate College → Ayertena","price":"2.0","distance_km":10.5,"stops":[{"sequence":1,"name":"Wingate School","latitude":8.975,"longitude":38.756},{"sequence":2,"name":"Ketena 2","latitude":8.98,"longitude":38.758},{"sequence":3,"name":"Ayertena","latitude":9.0703,"longitude":38.7449}]},
    {"route_code":"088","route_name":"Merkato → Chancho","price":"7.5","distance_km":40.0,"stops":[{"sequence":1,"name":"Merkato","latitude":9.0364,"longitude":38.7469},{"sequence":2,"name":"Piazza","latitude":9.0396,"longitude":38.7513},{"sequence":3,"name":"Chancho","latitude":9.2964,"longitude":38.5917}]},
    {"route_code":"089","route_name":"Merkato → Sendafa","price":"7.5","distance_km":44.0,"stops":[{"sequence":1,"name":"Merkato","latitude":9.0364,"longitude":38.7469},{"sequence":2,"name":"4 Kilo","latitude":9.0436,"longitude":38.7628},{"sequence":3,"name":"Sendafa","latitude":9.2039,"longitude":39.0126}]},
    {"route_code":"090","route_name":"Betel Hospital → Legehar","price":"2.0","distance_km":10.0,"stops":[{"sequence":1,"name":"Betel Hospital","latitude":9.0075,"longitude":38.7392},{"sequence":2,"name":"Torhailoch","latitude":8.9663,"longitude":38.7444},{"sequence":3,"name":"Legehar","latitude":9.0164,"longitude":38.7588}]},
    {"route_code":"091","route_name":"Merkato → Teji","price":"10.0","distance_km":52.0,"stops":[{"sequence":1,"name":"Merkato","latitude":9.0364,"longitude":38.7469},{"sequence":2,"name":"Torhailoch","latitude":8.9663,"longitude":38.7444},{"sequence":3,"name":"Teji","latitude":8.87,"longitude":38.52}]},
    {"route_code":"092","route_name":"Hana Mariam → Balcha Hospital","price":"2.0","distance_km":9.6,"stops":[{"sequence":1,"name":"Hana Mariam","latitude":9.062,"longitude":38.83},{"sequence":2,"name":"Sar Bet","latitude":9.0253,"longitude":38.7451},{"sequence":3,"name":"Balcha Hospital","latitude":9.0333,"longitude":38.7558}]},
    {"route_code":"093","route_name":"Bole Bulbula → Megenagna","price":"2.4","distance_km":15.2,"stops":[{"sequence":1,"name":"Bole Bulbula","latitude":8.962,"longitude":38.815},{"sequence":2,"name":"Bole Airport","latitude":8.9779,"longitude":38.799},{"sequence":3,"name":"Megenagna","latitude":9.0192,"longitude":38.8021}]},
    {"route_code":"094","route_name":"Piazza → Mekililand Birchko","price":"2.0","distance_km":9.9,"stops":[{"sequence":1,"name":"Piazza","latitude":9.0396,"longitude":38.7513},{"sequence":2,"name":"Pawlos","latitude":9.051,"longitude":38.731},{"sequence":3,"name":"Mekililand Birchko","latitude":9.058,"longitude":38.72}]},
    {"route_code":"095","route_name":"Merkato → Addisalem","price":"7.5","distance_km":47.0,"stops":[{"sequence":1,"name":"Merkato","latitude":9.0364,"longitude":38.7469},{"sequence":2,"name":"Fildoro","latitude":9.05,"longitude":38.708},{"sequence":3,"name":"Addisalem","latitude":8.98,"longitude":38.4}]},
    {"route_code":"096","route_name":"Megenagna → Goro Sefera","price":"1.4","distance_km":7.0,"stops":[{"sequence":1,"name":"Megenagna","latitude":9.0192,"longitude":38.8021},{"sequence":2,"name":"Anbessa Garage","latitude":9.02,"longitude":38.81},{"sequence":3,"name":"Goro Sefera","latitude":9.03,"longitude":38.835}]},
    {"route_code":"097","route_name":"Megenagna → Legetafo","price":"2.4","distance_km":15.8,"stops":[{"sequence":1,"name":"Megenagna","latitude":9.0192,"longitude":38.8021},{"sequence":2,"name":"Ayat Condominium","latitude":9.0367,"longitude":38.8503},{"sequence":3,"name":"Legetafo","latitude":9.12,"longitude":38.86}]},
    {"route_code":"098","route_name":"Dukem → Saris Abo","price":"4.5","distance_km":26.3,"stops":[{"sequence":1,"name":"Dukem","latitude":8.8255,"longitude":38.8091},{"sequence":2,"name":"Gelan","latitude":8.8869,"longitude":38.8222},{"sequence":3,"name":"Saris Abo","latitude":8.9748,"longitude":38.7925}]},
    {"route_code":"099","route_name":"Ayertena → Alemgena","price":"1.4","distance_km":8.3,"stops":[{"sequence":1,"name":"Ayertena","latitude":9.0703,"longitude":38.7449},{"sequence":2,"name":"Welete","latitude":8.96,"longitude":38.66},{"sequence":3,"name":"Alemgena","latitude":8.975,"longitude":38.69}]},
    {"route_code":"100","route_name":"Jemo Site → Merkato","price":"2.4","distance_km":14.5,"stops":[{"sequence":1,"name":"Jemo","latitude":8.9936,"longitude":38.7282},{"sequence":2,"name":"Dese Hotel","latitude":8.9936,"longitude":38.7282},{"sequence":3,"name":"Merkato","latitude":9.0364,"longitude":38.7469}]},
    {"route_code":"101","route_name":"Megenagna → Yeka Ayat Condominium","price":"2.0","distance_km":12.0,"stops":[{"sequence":1,"name":"Megenagna","latitude":9.0192,"longitude":38.8021},{"sequence":2,"name":"Ayat Condominium","latitude":9.0367,"longitude":38.8503},{"sequence":3,"name":"Yeka Ayat Condominium","latitude":9.05,"longitude":38.855}]},
    {"route_code":"102","route_name":"Legehar → Karalo","price":"2.4","distance_km":13.7,"stops":[{"sequence":1,"name":"Legehar","latitude":9.0164,"longitude":38.7588},{"sequence":2,"name":"Megenagna","latitude":9.0192,"longitude":38.8021},{"sequence":3,"name":"Karalo","latitude":8.86,"longitude":38.84}]},
    {"route_code":"103","route_name":"Jemo → Piazza","price":"2.4","distance_km":12.2,"stops":[{"sequence":1,"name":"Jemo","latitude":8.9936,"longitude":38.7282},{"sequence":2,"name":"Mexico","latitude":9.0258,"longitude":38.7538},{"sequence":3,"name":"Piazza","latitude":9.0396,"longitude":38.7513}]},
    {"route_code":"104","route_name":"Kera → Worku Sefer","price":"2.0","distance_km":12.0,"stops":[{"sequence":1,"name":"Kera","latitude":9.0022,"longitude":38.7538},{"sequence":2,"name":"Wehalimat","latitude":9.005,"longitude":38.762},{"sequence":3,"name":"Worku Sefer","latitude":9.0,"longitude":38.77}]},
    {"route_code":"105","route_name":"Legehar → Anfomeda","price":"2.0","distance_km":12.0,"stops":[{"sequence":1,"name":"Legehar","latitude":9.0164,"longitude":38.7588},{"sequence":2,"name":"Holland Embassy","latitude":9.015,"longitude":38.768},{"sequence":3,"name":"Anfomeda","latitude":9.02,"longitude":38.772}]},
    {"route_code":"106","route_name":"Megenagna → Goro","price":"2.0","distance_km":10.8,"stops":[{"sequence":1,"name":"Megenagna","latitude":9.0192,"longitude":38.8021},{"sequence":2,"name":"CMC","latitude":9.044,"longitude":38.8293},{"sequence":3,"name":"Goro Sefera","latitude":9.03,"longitude":38.835}]},
    {"route_code":"107","route_name":"Saris Abo → Akaki Korkoro Fabrica","price":"2.0","distance_km":11.4,"stops":[{"sequence":1,"name":"Saris Abo","latitude":8.9748,"longitude":38.7925},{"sequence":2,"name":"Kaliti","latitude":8.9513,"longitude":38.7799},{"sequence":3,"name":"Akaki","latitude":8.8798,"longitude":38.7994}]},
    {"route_code":"108","route_name":"Minilik Square → Asko Addisu Sefer","price":"2.0","distance_km":9.3,"stops":[{"sequence":1,"name":"Minilik Square","latitude":9.0441,"longitude":38.748},{"sequence":2,"name":"18 Mazoria","latitude":9.045,"longitude":38.74},{"sequence":3,"name":"Asko Sansuzi","latitude":9.068,"longitude":38.705}]},
    {"route_code":"109","route_name":"Saris Abo → Tulu Dimtu","price":"2.0","distance_km":12.0,"stops":[{"sequence":1,"name":"Saris Abo","latitude":8.9748,"longitude":38.7925},{"sequence":2,"name":"Kaliti","latitude":8.9513,"longitude":38.7799},{"sequence":3,"name":"Tulu Dimtu","latitude":8.93,"longitude":38.82}]},
    {"route_code":"110","route_name":"Akaki → 6 Kilo","price":"4.5","distance_km":24.9,"stops":[{"sequence":1,"name":"Akaki","latitude":8.8798,"longitude":38.7994},{"sequence":2,"name":"Meskel Square","latitude":9.0142,"longitude":38.7637},{"sequence":3,"name":"6 Kilo","latitude":9.053,"longitude":38.7698}]},
    {"route_code":"111","route_name":"Piazza → Burayu","price":"2.7","distance_km":16.6,"stops":[{"sequence":1,"name":"Piazza","latitude":9.0396,"longitude":38.7513},{"sequence":2,"name":"Medhanialem School","latitude":9.038,"longitude":38.749},{"sequence":3,"name":"Burayu","latitude":9.0431,"longitude":38.682}]},
    {"route_code":"112","route_name":"Circular Route — Ring Road","price":"2.0","distance_km":None,"stops":[{"sequence":1,"name":"Ring Road","latitude":None,"longitude":None}]},
]


def _fmt_coord(lat: float, lon: float) -> str:
    return f"({lat:.6f}, {lon:.6f})"


def main() -> None:
    session = SessionLocal()
    stop_cache: dict[str, str] = {}

    routes_inserted = 0
    routes_skipped = 0
    stops_inserted = 0
    stops_updated = 0
    stops_skipped = 0
    route_stops_added = 0

    try:
        with session.begin():
            # Upsert stops (by name) and build cache
            for route in ROUTES:
                for s in route["stops"]:
                    name = s["name"]
                    if name in stop_cache:
                        continue
                    lat = s.get("latitude")
                    lon = s.get("longitude")
                    if lat is None or lon is None:
                        print(f"[WARN]  Skipping stop '{name}' on route {route['route_code']} — missing coordinates")
                        stops_skipped += 1
                        continue
                    existing = session.execute(select(Stop).filter_by(name=name)).scalar_one_or_none()
                    if existing:
                        existing.latitude = lat
                        existing.longitude = lon
                        session.add(existing)
                        stops_updated += 1
                        print(f"[STOP]  Updated   '{name}'        {_fmt_coord(lat, lon)}")
                        stop_cache[name] = existing.id
                    else:
                        stop = Stop(id=str(uuid.uuid4()), name=name, latitude=lat, longitude=lon, created_at=datetime.utcnow())
                        session.add(stop)
                        session.flush()
                        stops_inserted += 1
                        print(f"[STOP]  Inserted  '{name}'        {_fmt_coord(lat, lon)}")
                        stop_cache[name] = stop.id

            # Insert routes and ensure route_stops exist for both new and existing routes
            for r in ROUTES:
                route_code = r["route_code"]
                existing_route = session.execute(select(Route).filter_by(route_code=route_code)).scalar_one_or_none()
                if existing_route:
                    routes_skipped += 1
                    route_obj = existing_route
                    print(f"[SKIP]  Route     '{route_code}'  already exists")
                else:
                    price = Decimal(r["price"]) if r.get("price") is not None else Decimal("0")
                    route_obj = Route(
                        id=str(uuid.uuid4()),
                        route_code=route_code,
                        route_name=r.get("route_name"),
                        price=price,
                        distance_km=r.get("distance_km"),
                        status=RouteStatus.ACTIVE,
                        is_deleted=False,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                    session.add(route_obj)
                    session.flush()
                    routes_inserted += 1
                    print(f"[ROUTE] Inserted  '{route_code}'  {r.get('route_name')}")

                # For both newly created and existing routes, ensure RouteStop rows exist
                for s in r["stops"]:
                    name = s["name"]
                    seq = s["sequence"]
                    lat = s.get("latitude")
                    lon = s.get("longitude")
                    if lat is None or lon is None:
                        print(f"[WARN]  Skipping stop '{name}' on route {route_code} — missing coordinates")
                        continue

                    stop_id = stop_cache.get(name)
                    # fallback to DB lookup if not in cache
                    if not stop_id:
                        found = session.execute(select(Stop).filter_by(name=name)).scalar_one_or_none()
                        if found:
                            stop_cache[name] = found.id
                            stop_id = found.id
                        else:
                            print(f"[WARN]  Skipping stop '{name}' on route {route_code} — not found in DB")
                            continue

                    # check if RouteStop already exists for this route and stop
                    existing_rs = session.execute(
                        select(RouteStop).filter_by(route_id=route_obj.id, stop_id=stop_id)
                    ).scalar_one_or_none()
                    if existing_rs:
                        continue

                    rs = RouteStop(id=str(uuid.uuid4()), route_id=route_obj.id, stop_id=stop_id, sequence=seq, created_at=datetime.utcnow())
                    session.add(rs)
                    route_stops_added += 1

    except Exception:
        session.rollback()
        traceback.print_exc()
        sys.exit(1)

    print("========================================")
    print("Seed complete.")
    print(f"  Routes  inserted : {routes_inserted}")
    print(f"  Routes  skipped  : {routes_skipped}")
    print(f"  Stops   inserted : {stops_inserted}")
    print(f"  Stops   updated  : {stops_updated}")
    print(f"  Stops   skipped  : {stops_skipped}  (missing coordinates)")
    print(f"  RouteStops added : {route_stops_added}")
    print("========================================")

    sys.exit(0)


if __name__ == "__main__":
    main()
