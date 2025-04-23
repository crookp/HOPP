import json
import pandas as pd
import numpy as np

import PySAM.Singleowner as Singleowner
from hopp.simulation import HoppInterface

HOURS_PER_YEAR = 8760
running_on_kestrel = False

# Simulate some sample data from an agent
# This data can either be saved in the agent dataframe directly, or be derived from the agent data 
agent_data = {
    "longitude": -103.65745,
    "latitude": 39.375683,
    "net_metering": 0,  # [0=net energy metering,1=net energy metering with $ credits,2=net billing,3=net billing with carryover to next month,4=buy all - sell all]
    "turbine_rating_kw": 250.0,
    "rotor_diameter": 40.0,
    "hub_height": 50.0,
    "solar_azimuth": 180.0,
    "solar_tilt": 20.0,
    "solar_capacity_kw": 250,
    "pv_to_batt_ratio": 1.21,
    "batt_capacity_to_power_ratio": 1,  # setting this to 2 doesn't converge?
    "load_schedule": np.ones(HOURS_PER_YEAR) * 10.0 / 1000.0,  # constant 10 kW for the whole year
    "urdb_label": "5ca4d1175457a39b23b3d45e",
    "power_curve_normalized": {
        1.0: 0.0,
        2.0: 0.0,
        3.0: 0.0,
        4.0: 0.022222222,
        5.0: 0.075555556,
        6.0: 0.146666667,
        7.0: 0.244444444,
        8.0: 0.368888889,
        9.0: 0.511111111,
        10.0: 0.662222222,
        11.0: 0.804444444,
        12.0: 0.915555556,
        13.0: 0.973333333,
        14.0: 0.995555556,
        15.0: 1.0,
        16.0: 1.0,
        17.0: 1.0,
        18.0: 1.0,
        19.0: 1.0,
        20.0: 1.0,
        21.0: 1.0,
        22.0: 1.0,
        23.0: 1.0,
        24.0: 1.0,
        25.0: 1.0,
        26.0: 0.0,
        27.0: 0.0,
        28.0: 0.0,
        29.0: 0.0,
    },
}

# Other inputs, which are made up of a combination of agent_data and constant assumptions that do not depend on the agent
num_turbines = 1
system_lifetime_years = 20

# There is the option to configure the PySAM financial model for each separate technology (wind, solar, etc)
# 
# We can load in the pre-configured defaults (e.g. WindPowerSingleOwner) from PySAM and then replace any parameters we
# like with non-default values, leaving the remainder untouched. I don't understand most of these parameters so I have
# left most things as-is, but just as an example I am changing the net metering policy
fin_model_wind_nondefault = {
    "ElectricityRates": {
        "ur_metering_option": agent_data["net_metering"],
    },
}
fin_model_wind = Singleowner.default("WindPowerSingleOwner")
fin_model_wind.assign(fin_model_wind_nondefault)

wind_layout_params = {"layout_x": [0.0], "layout_y": [0.0]}

# HOPP allows us to specify a `model_input_parameter` for wind that contains additional parameters that are passed to
# PySAM. I don't know what all these parameters do, I just exported a template file from SAM and populate it with the
# agent-specific values here

# This has required a small modification to HOPP - currently it only accepts a string for this `model_input_parameter`
# file which should be a path to a file. I made a slight modification to HOPP for it to accept a dict as well
with open("wind_config_template.json", "r") as f:
    pysam_wind_config = json.load(f)

pysam_wind_config["wind_turbine_rotor_diameter"] = agent_data["rotor_diameter"]
pysam_wind_config["wind_turbine_hub_ht"] = agent_data["hub_height"]
pysam_wind_config["system_capacity"] = agent_data["turbine_rating_kw"]
pysam_wind_config["wind_farm_xCoordinates"] = wind_layout_params["layout_x"]
pysam_wind_config["wind_farm_yCoordinates"] = wind_layout_params["layout_y"]
pysam_wind_config["wind_turbine_powercurve_windspeeds"] = agent_data["power_curve_normalized"].keys()
pysam_wind_config["wind_turbine_powercurve_powerout"] = [
    v * agent_data["turbine_rating_kw"]
    for v in agent_data["power_curve_normalized"].values()
]

wind_tech_config = {
    "num_turbines": num_turbines,
    "turbine_rating_kw": agent_data["turbine_rating_kw"],
    "rotor_diameter": agent_data["rotor_diameter"],
    "hub_height": agent_data["hub_height"],
    "turbine_name": None,
    "layout_mode": "custom",
    "model_name": "pysam",
    "layout_params": wind_layout_params,
    "adjust_air_density_for_elevation": True,
    "fin_model": fin_model_wind,
    "model_input_file": pysam_wind_config,
    "verbose": True,
}

fin_model_pv_nondefault = {
    "ElectricityRates": {
        "ur_metering_option": agent_data["net_metering"],
    },
}
fin_model_pv = Singleowner.default("PVWattsSingleOwner")
fin_model_pv.assign(fin_model_pv_nondefault)


pv_panel_system_design = {
    "array_type": 1.0,  # 0: fixed open rack 1: fixed roof mount 2: 1-axis tracking 3: 1-axis backtracking 4: 2-axis tracking
    "bifaciality": 0.0,  # monofacial modules have no bifaciality
    "module_type": 1.0,  # 0: standard 1: premium 2: thin film. Premium modules have an efficiency of 21%
    "losses": 15.0,  # DC-losses represented as a percentage
    # inverter specifications. Inverters convert DC-power from the solar panels to AC-power
    "dc_ac_ratio": 1.2,  # inverter is (1/dc_ac_ratio) the capacity of the pv system.
    "inv_eff": 95.0,  # inverter efficiency as a percentage
    # panel layout and orientation
    "gcr": 0.3,  # groud coverage ratio default value
    "azimuth": agent_data["solar_azimuth"],  # South-facing panels. East is 90, South is 180, West is 270
    "rotlim": 0.0,  # no rotational limit because using a fixed-tilt panel
}

pv_tech_config = {
    "system_capacity_kw": agent_data["solar_capacity_kw"],
    "use_pvwatts": True,
    "dc_ac_ratio": pv_panel_system_design["dc_ac_ratio"],  # why is this specified both here and in pv_panel_system_design?
    "inv_eff": pv_panel_system_design["inv_eff"],  # why is this specified both here and in pv_panel_system_design?
    "losses": 10.0,
    "fin_model": "FlatPlatePVSingleOwner",
    "dc_degradation": [1.5] * system_lifetime_years,
    "approx_nominal_efficiency": 18.0,
    "panel_system_design": pv_panel_system_design,
    "panel_tilt_angle": agent_data["solar_tilt"],
    "module_unit_mass": None,
}


fin_model_battery = Singleowner.default("CustomGenerationBatterySingleOwner")
fin_model_battery_nondefault = {
    "ElectricityRates": {
        "ur_metering_option": agent_data["net_metering"],
    },
}

battery_capacity_kw = agent_data["solar_capacity_kw"] * agent_data["pv_to_batt_ratio"]
battery_capacity_kwh = battery_capacity_kw * agent_data["batt_capacity_to_power_ratio"]

fin_model_battery.assign(fin_model_battery_nondefault)
battery_tech_config = {
    "tracking": True,
    "system_capacity_kw": battery_capacity_kw,
    "system_capacity_kwh": battery_capacity_kwh,
    "minimum_SOC": 10,  # I have left this as constant for now
    "maximum_SOC": 90,  # I have left this as constant for now
    "initial_SOC": 50,  # I have left this as constant for now
    "fin_model": fin_model_battery,
}

# interconnect_kw for grid is required, I have just set it to the sum of the wind, pv and battery capacities
grid_tech_config = {
    "interconnect_kw": (
        wind_tech_config["turbine_rating_kw"]
        + pv_tech_config["system_capacity_kw"]
        + battery_tech_config["system_capacity_kw"]
    ),
}

site_config = {
    "data": {
        "lon": agent_data["longitude"],
        "lat": agent_data["latitude"],
        "elev": None,  # what does this do other than impact air density
        "year": 2014,
        "urdb_label": agent_data["urdb_label"],
        "site_details": {
            "site_area_m2": 0.0,  # is there any harm in setting this to zero? (For one turbine)
            "site_shape": "circle",
            "x0": 0.0,
            "y0": 0.0,
        },
    },
    "hub_height": wind_tech_config["hub_height"],
    "solar": True,
    "wind": True,
    "desired_schedule": agent_data["load_schedule"],
    "renewable_resource_origin": "HPC" if running_on_kestrel else "API",
}

hopp_config = {
    "name": "hopp_test",
    "site": site_config,
    "technologies": {
        "wind": wind_tech_config,
        "pv": pv_tech_config,
        "grid": grid_tech_config,
        "battery": battery_tech_config,
    },
    "config": {
        "dispatch_options": {
            "solver": "cbc",
            "battery_dispatch": "simple",
            "grid_charging": True,
            "pv_charging_only": False,
            "include_lifecycle_count": False,
            "is_test_start_year": True,  # for testing
        },
        "cost_info": {},
        "simulation_options": {
            "wind": {},
            "solar": {},
        },
    },
}

hi = HoppInterface(hopp_config)
hi.simulate(system_lifetime_years)

for tech in ["wind", "pv", "battery", "hybrid"]:
    if tech != "hybrid":
        print(f"{tech:<8s} {'installed cost':<14s}: ${getattr(hi.system, tech).total_installed_cost/1000:,.0f}k")
    print(f"{tech:<8s} {'NPV':<14s}: ${getattr(hi.hopp.system.net_present_values, tech)/1000:,.0f}k")
    print(f"{tech:<8s} {'LCOE':<14s}: ${getattr(hi.hopp.system.lcoe_real, tech)*100:,.1f}/kWh")

# %%
