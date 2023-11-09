################################################################################
# @author: Seongeun Jeong, LBNL
# @note: this script downloads the ERA5 "model-level" data. Particularly, this 
#   script downloads the U and V wind components at the model levels.
################################################################################
#!/usr/bin/env python
# Install cdsapi
# See https://cds.climate.copernicus.eu/api-how-to
import cdsapi
c = cdsapi.Client()

import calendar
import os.path

################################################################################
# Options
################################################################################
YEARS = range (2019, 2020)

PATH_OUT = './'

################################################################################
# User-defined region (of the US): this is due to the file size is too big.
#   Depending on the user's computational resources, the user can change the region.
################################################################################
REGION = 'NW'

if REGION == 'NW':
    xmin_max = [-125, -116]
    ymin_max = [41,50]
    area_ = str(ymin_max[1])+'/'+str(xmin_max[0]) + '/' + str(ymin_max[0]) + '/' + \
                str (xmin_max[1])
    print (area_)
    file_path = PATH_OUT

#...............................................................................
# For other regions, specify the region and the area.
#...............................................................................
else:
    print ('REGION: {}'.format (REGION))

assert os.path.exists(file_path)
print ('Processing: {}'.format (REGION))

################################################################################
# Data download specifications
# From ERA5 documentation (the website info can be changed)
################################################################################
cls = "ea"                              # do not change
dataset = "era5"                        # do not change
expver = "1"                            # do not change
levtype = "ml"                          # do not change
stream = "oper"                         # do not change
tp = "an"                               # type: Use "an" (analysis) unless you have a particular reason to use "fc" (forecast).
time = "00:00:00/to/23:00:00/by/1"      #"00:00:00/to/23:00:00/by/1" time: ERA5 data is hourly. Specify a single time as "00:00:00", or a range as "00:00:00/01:00:00/02:00:00" or "00:00:00/to/23:00:00/by/1".
step = "0"                              # step: With type=an, step is always "0"
grid = "0.25/0.25"                      # grid: Any supported regular or Gaussian grid. Spectral ("sh") is not supported. We recommend lat/long at 0.25/0.25 deg.
area = area_                            # area: N/W/S/E; here we get data for Europe.
levelist = "128/129/130/131/132/133/134/135/136/137" # Specify the levels

################################################################################
# Iterate
################################################################################
for year in YEARS: 
        print ('YEAR: {}'.format (year))

        ################################################################################
        # Change the months!!!
        #   => This is due to the file size, but the user can change it to the whole year.
        ################################################################################
        bdate = str(year)+'0101'
        edate = str(year)+'0131'

        file_out = file_path + "ERA5_UV_ml_%s_%s_%s.nc"%(bdate,edate, REGION)
        print ('Outfile: {}'.format (file_out))

        print ("######### ERA-5 ################")
        print ('get data from ', bdate,' to ',edate,' (YYYYMMDD)')
        print ("################################")

        c.retrieve('reanalysis-era5-complete', {
                    "class": cls,
                    "dataset": dataset,
                    "expver": expver,
                    "levtype": levtype,
                    "stream": stream,
                    "date" : "%s/to/%s"%(bdate,edate),
                    "type": tp,
                    "time": time,
                    "step": step,
                    "grid": grid,
                    "area": area,
                    "param": "131/132",         # U and V; refer to the ERA5 documentation for the parameter code.
                    "levelist": levelist,       # for each of the 137 model levels
                    "format": "netcdf",          # NOTE: this is optional for netcdf; for grib, remove this line
                }, file_out)
        
