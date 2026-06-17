# Processing & loading — telemetry

## Transformation (text → value)
- _(none)_

## Imputation
- _(none)_

## Outliers (IQR clip)
- `temperature_c`: 111 clipped to [31.915, 62.195]
- `pressure_bar`: 547 clipped to [189.524, 207.612]
- `voltage_mean_v`: 389 clipped to [221.41, 233.73]
- `rotation_mean_rpm`: 46 clipped to [1326.2, 1815.8]
- `pieces_produced`: 0 clipped to [-29.5, 126.5]

## Database load

- 134280 rows loaded into table 'telemetry'
