"""Build the static 2024 city comparison from archived Open-Meteo ERA5 responses.

Install scripts/requirements_heat_stress.txt into a virtual environment first.
The source folder contains raw/{city}-era5-2024.json and
open-meteo-provenance.json, produced by fetch_heat_stress_data.py.
No network requests are made by this builder. Every input hour and source hash is
checked before nonlinear indices are calculated at their original hourly scale.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
START = datetime(2024, 1, 1, tzinfo=timezone.utc)
HOURS = 8784
OFFSETS = {'seoul': 9, 'pyeongtaek': 9, 'london': 0, 'beijing': 8, 'los-angeles': -8}
EXPECTED = {'numpy': '2.3.5', 'thermofeel': '2.3.0', 'earthkit-meteo': '1.2.1'}
FIELDS = {
    'temperature': 'temperature_2m', 'humidity': 'relative_humidity_2m',
    'dewpoint': 'dew_point_2m', 'windSpeed10m': 'wind_speed_10m',
    'surfacePressure': 'surface_pressure', 'shortwaveRadiation': 'shortwave_radiation_instant',
    'directRadiation': 'direct_radiation_instant',
}


def write_json(path, content, *, indent=None):
    raw = (json.dumps(content, ensure_ascii=False, allow_nan=False, indent=indent,
                      separators=None if indent else (',', ':')) + '\n').encode('utf-8')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def quantize(values):
    """Retain 0.1-unit input/output precision; nonfinite estimates are missing."""
    return [None if not np.isfinite(value) else float(round(float(value), 1)) for value in values]


def reference_validation():
    """Independent published/package reference cases, not app-generated goldens."""
    # pythermalcomfort's documented SI example: 25 C, MRT25 C, v10=1 m/s,
    # RH50% -> UTCI24.6 C. Full precision retains thermofeel's polynomial result.
    t = np.array([298.15])
    vapour = tmf.calculate_saturation_vapour_pressure(t) * .5
    result = float(tmf.calculate_utci(t, np.array([1.0]), t, ehPa=vapour)[0] - 273.15)
    assert abs(result - 24.6) < .05, f'UTCI reference mismatch: {result}'
    # ECMWF thermofeel/tests first published CSV case. Values and expected
    # results are separate upstream files, not derived from this script.
    air = np.array([310.0])
    dewpoint = np.array([280.0])
    rh = tmf.calculate_relative_humidity_percent(air, dewpoint)
    utci = float(tmf.calculate_utci(air, np.array([2.0]), np.array([300.0]), td_k=dewpoint)[0])
    assert abs(utci - 306.5924867914496) < 1e-6, f'UTCI upstream regression mismatch: {utci}'
    wbgt = float(tmf.calculate_wbgt_liljegren(
        air, rh, np.array([1013.25]), np.array([2.0]),
        np.array([604146.4934 / 3600]), np.array([374150.1613 / 604146.4934]), np.array([.5]),
    )[0])
    assert abs(wbgt - 298.4340833516603) < 1e-6, f'WBGT upstream regression mismatch: {wbgt}'
    # Solar-position convention catches degrees/radians, longitude sign and UTC
    # mistakes: equatorial noon near equinox has a high sun; midnight has none.
    equinox_noon = float(cos_solar_zenith_angle(datetime(2024, 3, 20, 12), np.array([0]), np.array([0]))[0])
    midnight = float(cos_solar_zenith_angle(datetime(2024, 3, 20, 0), np.array([0]), np.array([0]))[0])
    assert equinox_noon > .99 and midnight == 0, 'Solar-position convention mismatch'
    return {'passed': True, 'utciExampleCelsius': round(result, 8),
            'utciUpstreamKelvin': round(utci, 8), 'wbgtUpstreamKelvin': round(wbgt, 8),
            'source': 'https://github.com/ecmwf/thermofeel/tree/2.3.0/tests',
            'utciExampleSource': 'https://pythermalcomfort.readthedocs.io/en/stable/_modules/pythermalcomfort/models/utci.html'}


def calculate(inputs, cosine):
    air, humidity, wind, pressure = (inputs[key] for key in ['temperature', 'humidity', 'windSpeed10m', 'surfacePressure'])
    kelvin = air + 273.15
    vapour = tmf.calculate_saturation_vapour_pressure(kelvin) * humidity / 100
    # A disclosed calm-wind floor preserves calm hours without polynomial
    # extrapolation. Values above the model's other limits are omitted.
    adjusted_wind = np.maximum(wind, .5)
    valid = ((air >= -50) & (air <= 50) & (humidity >= 0) & (humidity <= 100)
             & (wind >= 0) & (wind <= 17) & (vapour >= 0) & (vapour <= 50))
    utci = tmf.calculate_utci(kelvin, adjusted_wind, kelvin, ehPa=vapour) - 273.15
    utci = np.where(valid, utci, np.nan)

    solar = np.maximum(inputs['shortwaveRadiation'], 0)
    direct = np.maximum(inputs['directRadiation'], 0)
    fraction = np.divide(direct, solar, out=np.zeros_like(solar), where=solar > 0)
    wbgt = tmf.calculate_wbgt_liljegren(kelvin, humidity, pressure, wind, solar, fraction, cosine) - 273.15
    # Shade is a controlled scenario: zero shortwave at the sensors while
    # retaining the ambient atmosphere's wind profile. The no-solar-load WBGT
    # weights differ from the outdoor solar-load expression.
    sensor_wind = tmf.calculate_wind_speed_2m_liljegren(np.maximum(wind, .62), cosine, solar)
    guarded_fraction = np.where(cosine < liljegren.CZA_MIN, 0, np.clip(fraction, 0, .9))
    exposed_wetbulb = liljegren.solve_wetbulb(
        kelvin, humidity / 100, pressure, sensor_wind, solar, guarded_fraction, cosine, 1.0,
    )
    zeros = np.zeros_like(solar)
    globe = liljegren.solve_globe(kelvin, humidity / 100, pressure, sensor_wind, zeros, zeros, cosine)
    wetbulb = liljegren.solve_wetbulb(kelvin, humidity / 100, pressure, sensor_wind, zeros, zeros, cosine, 1.0)
    shade = .7 * wetbulb + .3 * globe
    # Conservative application filter, not a published whole-model domain:
    # the evaporation-property helper is fitted for 283..313 K at the mean of
    # air and natural-wet-bulb temperature. Do not extrapolate that property
    # outside its documented fit in the values exposed by the application.
    exposed_reference = (kelvin + exposed_wetbulb + 273.15) / 2
    shade_reference = (kelvin + wetbulb + 273.15) / 2
    exposed_fit = (exposed_reference >= 283) & (exposed_reference <= 313)
    shade_fit = (shade_reference >= 283) & (shade_reference <= 313)
    wbgt_nonconvergent = ~np.isfinite(wbgt)
    shade_nonconvergent = ~np.isfinite(shade)
    wbgt = np.where(exposed_fit, wbgt, np.nan)
    shade = np.where(shade_fit, shade, np.nan)
    diagnostics = {
        'utciWindFloorHours': int(((wind < .5) & valid).sum()),
        'utciOutsideDomainHours': int((~valid).sum()),
        'utciMissingHours': int((~np.isfinite(utci)).sum()),
        'wbgtWindFloorHours': int((wind < .62).sum()),
        'wbgtDirectFractionCappedHours': int(((fraction > .9) & (cosine >= .00873)).sum()),
        'wbgtNonconvergentHours': int(wbgt_nonconvergent.sum()),
        'wbgtShadeNonconvergentHours': int(shade_nonconvergent.sum()),
        'wbgtOutsidePropertyFitHours': int((~exposed_fit & ~wbgt_nonconvergent).sum()),
        'wbgtShadeOutsidePropertyFitHours': int((~shade_fit & ~shade_nonconvergent).sum()),
        'wbgtMissingHours': int((~np.isfinite(wbgt)).sum()),
        'wbgtShadeMissingHours': int((~np.isfinite(shade)).sum()),
        'subfreezingAirHours': int((air < 0).sum()),
    }
    return {'utci': utci, 'wbgt': wbgt, 'wbgtShade': shade}, diagnostics


def build(source_root, destination):
    provenance = json.loads((source_root / 'open-meteo-provenance.json').read_text(encoding='utf-8'))
    validation = reference_validation()
    manifest = {
        'schemaVersion': 1, 'year': 2024, 'startUtc': '2024-01-01T00:00:00Z',
        'intervalMinutes': 60, 'hours': HOURS,
        'dataset': 'ERA5 reanalysis accessed via Open-Meteo Historical Weather API',
        'dataKind': 'Gridded reanalysis estimates; not city monitoring-station observations.',
        'spatialSelection': 'Nearest native ERA5 grid point; elevation adjustment disabled (elevation=nan).',
        'calendar': 'Full UTC year. Fixed local standard-time offsets are available for aggregation; daylight saving time is not applied.',
        'precision': 'Stored values rounded to 0.1 C, 0.1 percentage point or 0.1 input unit; app summaries and counts use these retained hourly values.',
        'software': EXPECTED, 'validation': validation,
        'metrics': {
            'temperature': {'label': 'Air temperature', 'unit': '°C', 'method': 'ERA5 2 m air temperature.'},
            'humidity': {'label': 'Relative humidity', 'unit': '%', 'method': 'Open-Meteo relative humidity at 2 m from ERA5.'},
            'utci': {'label': 'UTCI · no added radiant heat', 'unit': '°C',
                     'method': 'Bröde sixth-order polynomial through thermofeel. Mean radiant temperature equals air temperature: a no-added-radiant-heat scenario, not observed urban shade or full-sun UTCI. Humidity converted to vapour pressure with thermofeel Hardy saturation pressure.',
                     'wind': 'ERA5 10 m wind; values below 0.5 m/s raised to 0.5 m/s and counted in diagnostics.',
                     'domain': 'Air -50 to 50 C; 10 m wind no more than 17 m/s; vapour pressure no more than 50 hPa; RH 0 to 100%. Out-of-domain values are null.',
                     'heatThresholdsCelsius': [26, 32, 38, 46]},
            'wbgt': {'label': 'WBGT · exposed outdoors', 'unit': '°C',
                     'method': 'Physically based Liljegren energy-balance model through thermofeel.calculate_wbgt_liljegren. WBGT = 0.7 natural wet-bulb + 0.2 globe + 0.1 air temperature. Solar radiation uses Open-Meteo instantaneous-time estimates; cosine of solar zenith uses earthkit-meteo at the returned grid point and UTC timestamp.',
                     'wind': 'KNMI/Liljegren stability-dependent 10 m to 2 m conversion; 10 m floor 0.62 m/s, internal 2 m floor 0.13 m/s.',
                     'radiation': 'Direct-horizontal/global-horizontal fraction; package caps fraction at 0.9 and removes direct beam at zenith above 89.5 degrees. Default Liljegren clear-sky atmospheric emissivity, surface temperature equal to air temperature, surface albedo 0.45 and emissivity 0.999 retained. No measured street-scale radiative environment.',
                     'propertyFitFilter': 'Conservative application filter, not a published whole-model validity range: omit hours when the converged mean of air and natural-wet-bulb temperature is outside 283 to 313 K, the documented fit range of the latent-heat property helper. Each WBGT scenario is filtered separately. Summary averages are conditional on retained hours; omitted hours are not zero or known below threshold.',
                     'interpretation': 'Historical screening estimate, not a measured workplace WBGT, work/rest prescription or compliance determination. Interpretation depends on workload, clothing and acclimatization. WBGT is not a cold-stress measure.'},
            'wbgtShade': {'label': 'WBGT · no shortwave radiation', 'unit': '°C',
                          'method': 'Same Liljegren sensor energy-balance solvers and ambient wind profile, with all shortwave radiation at the sensors removed. No-solar-load WBGT = 0.7 natural wet-bulb + 0.3 globe temperature. Longwave model assumptions remain; this does not reconstruct actual shade at a site. The same 283 to 313 K property-fit application filter is applied using this scenario\'s natural-wet-bulb temperature.'},
        },
        'references': [
            {'title': 'Open-Meteo Historical Weather API', 'url': 'https://open-meteo.com/en/docs/historical-weather-api'},
            {'title': 'Open-Meteo attribution and licence', 'url': 'https://open-meteo.com/en/licence'},
            {'title': 'thermofeel UTCI and WBGT implementation', 'url': 'https://github.com/ecmwf/thermofeel/blob/2.3.0/thermofeel/thermofeel.py'},
            {'title': 'Bröde et al. UTCI operational procedure', 'url': 'https://doi.org/10.1007/s00484-011-0454-1'},
            {'title': 'Liljegren et al. WBGT model', 'url': 'https://doi.org/10.1080/15459620802310770'},
            {'title': 'pythermalcomfort WBGT solar/no-solar weighting', 'url': 'https://pythermalcomfort.readthedocs.io/en/stable/_modules/pythermalcomfort/models/wbgt.html'},
            {'title': 'earthkit-meteo solar geometry', 'url': 'https://earthkit-meteo.readthedocs.io/en/stable/autoapi/earthkit/meteo/solar/index.html'},
            {'title': 'NWS comparison of WBGT and heat index', 'url': 'https://www.weather.gov/sgf/wbgt'},
        ],
        'records': [],
    }
    expected_time = [(START + timedelta(hours=hour)).strftime('%Y-%m-%dT%H:%M') for hour in range(HOURS)]
    for source in provenance['sources']:
        city_id = source['id']
        raw_path = source_root / 'raw' / source['file']
        raw_bytes = raw_path.read_bytes()
        assert hashlib.sha256(raw_bytes).hexdigest() == source['sha256'], f'{city_id}: source SHA256 mismatch'
        raw = json.loads(raw_bytes)
        assert raw['hourly']['time'] == expected_time, f'{city_id}: not the complete UTC2024 hourly grid'
        assert raw['utc_offset_seconds'] == 0, f'{city_id}: source time zone must be UTC'
        assert raw['hourly_units']['wind_speed_10m'] == 'm/s', f'{city_id}: wind unit mismatch'
        assert raw['hourly_units']['surface_pressure'] == 'hPa', f'{city_id}: pressure unit mismatch'
        inputs = {key: np.asarray(raw['hourly'][field], dtype=float) for key, field in FIELDS.items()}
        assert all(len(values) == HOURS and np.isfinite(values).all() for values in inputs.values()), f'{city_id}: incomplete/nonfinite inputs'
        assert (inputs['humidity'] >= 0).all() and (inputs['humidity'] <= 100).all()
        assert (inputs['windSpeed10m'] >= 0).all() and (inputs['surfacePressure'] > 0).all()
        # earthkit's array implementation accepts a single date with array-like
        # coordinates. A single time loop avoids hidden timezone conversion.
        latitude, longitude = np.array([raw['latitude']]), np.array([raw['longitude']])
        cosine = np.array([float(cos_solar_zenith_angle(
            (START + timedelta(hours=hour)).replace(tzinfo=None), latitude, longitude,
        )[0]) for hour in range(HOURS)])
        computed, diagnostics = calculate(inputs, cosine)
        values = {key: quantize(inputs[key]) for key in ['temperature', 'humidity']}
        values.update({key: quantize(value) for key, value in computed.items()})
        # Retain driving weather inputs beside the plotted metrics, so exported
        # hours can be independently inspected without repeating acquisition.
        record = {
            'id': city_id, 'city': source['city'], 'year': 2024,
            'startUtc': '2024-01-01T00:00:00Z', 'intervalMinutes': 60,
            'latitude': source['requestedLatitude'], 'longitude': source['requestedLongitude'],
            'gridLatitude': raw['latitude'], 'gridLongitude': raw['longitude'],
            'gridElevationMetres': raw['elevation'], 'utcOffsetHours': OFFSETS[city_id],
            'civilTimezone': source['civilTimezone'], 'values': values,
            'inputs': {key: quantize(value) for key, value in inputs.items() if key not in ['temperature', 'humidity']},
            'diagnostics': diagnostics,
            'source': {'url': source['url'], 'retrievedAt': source['retrievedAt'], 'sha256': source['sha256'],
                       'dataKind': 'ERA5 reanalysis grid estimate'},
        }
        filename = f'{city_id}-2024.json'
        checksum = write_json(destination / filename, record)
        manifest['records'].append({'id': city_id, 'city': source['city'], 'file': f'data/{filename}',
                                    'sha256': checksum, 'sourceSha256': source['sha256'], 'hours': HOURS,
                                    'gridLatitude': raw['latitude'], 'gridLongitude': raw['longitude'],
                                    'utcOffsetHours': OFFSETS[city_id], 'diagnostics': diagnostics})
        print(f'{source["city"]}: {HOURS} hourly values; {diagnostics}')
    assert len(manifest['records']) == 5 and any(record['id'] == 'seoul' for record in manifest['records'])
    write_json(destination / 'manifest.json', manifest, indent=2)
    print(f'Built {len(manifest["records"])} records; reference cases passed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=ROOT.parent / 'heat-stress-comparison' / 'research')
    parser.add_argument('--destination', type=Path, default=ROOT / 'projects' / 'heat-stress' / 'data')
    parser.add_argument('--dependency-dir', type=Path, help='Optional task-local pip --target directory.')
    parser.add_argument('--validate-only', action='store_true', help='Run independent reference cases without writing data.')
    args = parser.parse_args()
    if args.dependency_dir:
        sys.path.insert(0, str(args.dependency_dir.resolve()))
    import numpy as np
    import thermofeel as tmf
    from thermofeel import liljegren
    from earthkit.meteo.solar import cos_solar_zenith_angle
    for package, expected in EXPECTED.items():
        assert version(package) == expected, f'{package}: install pinned version {expected} from requirements_heat_stress.txt'
    if args.validate_only:
        print(json.dumps(reference_validation(), indent=2))
    else:
        build(args.source_root, args.destination)
