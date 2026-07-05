from jarvis.skills.business_metrics import calculate_hospitality_kpis, calculate_marketing_kpis
from jarvis.skills.filesystem import write_text_file

HOTEL_CSV = (
    "date,property,rooms_available,rooms_sold,room_revenue\n"
    "2026-01-01,Beachfront,100,80,16000\n"
    "2026-01-02,Beachfront,100,90,19800\n"
    "2026-01-01,Hillside,50,25,3750\n"
)

ADS_CSV = (
    "campaign,impressions,clicks,spend,conversions,revenue\n"
    "Search,10000,500,1000,50,5000\n"
    "Display,20000,200,400,10,800\n"
)


def test_hospitality_kpis_overall():
    write_text_file("hotel.csv", HOTEL_CSV, overwrite=True)
    result = calculate_hospitality_kpis(
        path="hotel.csv",
        rooms_available_col="rooms_available",
        rooms_sold_col="rooms_sold",
        room_revenue_col="room_revenue",
    )
    overall = result["overall"]
    assert overall["rooms_available"] == 250
    assert overall["rooms_sold"] == 195
    assert overall["total_revenue"] == 39550
    assert overall["occupancy_rate"] == round(195 / 250, 4)
    assert overall["adr"] == round(39550 / 195, 2)
    assert overall["revpar"] == round(39550 / 250, 2)


def test_hospitality_kpis_grouped_by_property():
    write_text_file("hotel2.csv", HOTEL_CSV, overwrite=True)
    result = calculate_hospitality_kpis(
        path="hotel2.csv",
        rooms_available_col="rooms_available",
        rooms_sold_col="rooms_sold",
        room_revenue_col="room_revenue",
        group_by="property",
    )
    assert set(result["by_group"].keys()) == {"Beachfront", "Hillside"}
    assert result["by_group"]["Hillside"]["occupancy_rate"] == round(25 / 50, 4)


def test_hospitality_kpis_missing_column():
    write_text_file("hotel3.csv", HOTEL_CSV, overwrite=True)
    result = calculate_hospitality_kpis(
        path="hotel3.csv",
        rooms_available_col="nonexistent",
        rooms_sold_col="rooms_sold",
        room_revenue_col="room_revenue",
    )
    assert "error" in result


def test_marketing_kpis_with_roas():
    write_text_file("ads.csv", ADS_CSV, overwrite=True)
    result = calculate_marketing_kpis(
        path="ads.csv",
        impressions_col="impressions",
        clicks_col="clicks",
        spend_col="spend",
        conversions_col="conversions",
        revenue_col="revenue",
    )
    overall = result["overall"]
    assert overall["impressions"] == 30000
    assert overall["clicks"] == 700
    assert overall["spend"] == 1400
    assert overall["conversions"] == 60
    assert overall["ctr"] == round(700 / 30000, 4)
    assert overall["cpc"] == round(1400 / 700, 2)
    assert overall["cpa"] == round(1400 / 60, 2)
    assert overall["roas"] == round(5800 / 1400, 3)


def test_marketing_kpis_without_revenue_omits_roas():
    write_text_file("ads2.csv", ADS_CSV, overwrite=True)
    result = calculate_marketing_kpis(
        path="ads2.csv",
        impressions_col="impressions",
        clicks_col="clicks",
        spend_col="spend",
        conversions_col="conversions",
    )
    assert "roas" not in result["overall"]


def test_marketing_kpis_grouped_by_campaign():
    write_text_file("ads3.csv", ADS_CSV, overwrite=True)
    result = calculate_marketing_kpis(
        path="ads3.csv",
        impressions_col="impressions",
        clicks_col="clicks",
        spend_col="spend",
        conversions_col="conversions",
        group_by="campaign",
    )
    assert set(result["by_group"].keys()) == {"Search", "Display"}
    assert result["by_group"]["Search"]["cpc"] == round(1000 / 500, 2)
