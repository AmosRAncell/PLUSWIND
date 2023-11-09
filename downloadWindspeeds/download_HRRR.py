################################################################################
# @author: Seongeun Jeong, LBNL
# @note: This scripts downloads the HRRR hourly 80-m wind data 
#           using the "herbie" package.
################################################################################

from herbie import Herbie #https://github.com/blaylockbk/Herbie
import pandas as pd
import numpy as np
import sys
import importlib
from os.path import expanduser
import os
HOME = expanduser("~")

################################################################################
# Functions
################################################################################
def get_dates_month (year, month, time_zone = 'GMT'):
    # format: '2020-01-01 01:00'
    days_in_month = pd.Timestamp(int(year), int(month),1).daysinmonth
    print ('Days in month {}'.format (days_in_month))

    dt = pd.date_range(start=year+ '-' + month + '-01-00', \
            end = year + '-' + month + '-' + str(days_in_month) + '-23', tz=time_zone, freq='1H')

    dt = dt.strftime ('%Y-%m-%d %H:%M')
    return (dt)

def download (H, var):
    H.download(var)

################################################################################
# Options
################################################################################
YEAR = '2021'

MONTHS = range (1, 2)  # 1 - 12
PRIORITY = ['google', 'pando', 'nomads'] # Priority for downloading data from the server    

PATH_OUT = './'

################################################################################
# Variable
#   Note: see: https://rapidrefresh.noaa.gov/hrrr/HRRRv4_GRIB2_WRFTWO.txt
################################################################################
#VAR = "UGRD:80 m" # Long name: #"UGRD:80 m above ground:anl"
VAR = "VGRD:80 m" # Long name: #"VGRD:80 m above ground:anl"

# Product: 80-m winds are available in the "sfc" product.
PRODUCT = 'sfc'

################################################################################
# Iterate by months for a specific year:
#   The user can specify the months to download.
#   The user can also specify the list of datetime objects to download in a 
#   different way.
################################################################################
for this_month in MONTHS:

    #===============================================================================
    # Get dates
    #===============================================================================
    # Get string format
    this_month_str = str(this_month).zfill (2)
    dt = get_dates_month (YEAR, this_month_str).to_numpy()
    assert np.array_equal (sorted (dt), dt)
    
    #===============================================================================
    # Iterate for each hour for the month
    #===============================================================================
    for this_dt in dt:
        print (this_dt)
    
        #===============================================================================
        # Construct H object
        #===============================================================================
        H = Herbie(this_dt,
                model = 'hrrr',
                product = PRODUCT,
                fxx=0, # 0 is analysis!!!
                save_dir = PATH_OUT,
                priority=PRIORITY) 

        #===============================================================================
        # Download
        #===============================================================================
        try:
            download (H, VAR)
        except Exception:
            print ('\nlikely no data\n')
            pass

print ('ALL DONE')

