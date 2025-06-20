#!/usr/bin/env python3

# Create discrete inventory from lancube data
# Author : Julien-Pierre Houle


import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from scipy.ndimage import gaussian_filter1d
from cleaning_data import *
#from src.gaussian_filter import *
from lights_distance import *
import warnings
import datetime
import yaml
from io import StringIO
warnings.filterwarnings("ignore",category=RuntimeWarning)
pd.options.mode.chained_assignment = None


# Load  Parameters
with open("input_params.in") as f:
    p = yaml.safe_load(f)
    
PATH_DATAS = p['PATH_DATAS']
filename = p['filename']
h = p['h']
K = p['K']
prec_localisation = p['prec_localisation']

# First load the data in and remove null characters.
# This is being inputted by the LANcube during recording and will prevent the
# rest of the pipeline from working. 
with open(f"{filename}", 'r') as fh:
    input_text = fh.read()
input_text = input_text.replace('\x00', '')
# Reading Lan3 datas
# df = pd.read_csv(f"{filename}", sep=',', on_bad_lines='skip')
df = pd.read_csv(StringIO(input_text), sep=',', on_bad_lines='skip')
df['Value'] = df['Clear'] / df['Gain'] / df['AcquisitionTime(ms)']


# Correction temps acquision des couleurs
df['Red_i']   = df['Red']   / df['Gain'] / df['AcquisitionTime(ms)']
df['Green_i'] = df['Green'] / df['Gain'] / df['AcquisitionTime(ms)']
df['Blue_i']  = df['Blue']  / df['Gain'] / df['AcquisitionTime(ms)']
df['Clear']   = df['Clear'] / df['Gain'] / df['AcquisitionTime(ms)']

# Removing Infrared from RGB
df['Red']   = (df['Red_i']   - df['Blue_i'] - df['Green_i'] + df['Clear']) / 2
df['Green'] = (df['Green_i'] - df['Red_i']  - df['Blue_i']  + df['Clear']) / 2
df['Blue']  = (df['Blue_i']  - df['Red_i']  - df['Green_i'] + df['Clear']) / 2

# Calculating IR
df['IR'] = (df['Red_i'] + df['Blue_i'] + df['Green_i'] - df['Clear']) / 2


# Cleaning dataframes
df1, df3, df5 = cleaning_data(df)
df_initial = pd.concat([df1, df3, df5], ignore_index=True)


# Remove the first 10 meters of datas
# But use the calculatuion of the mean distance, else we may (and have) accidentally
# cut off some rows from some sensors and not from others, causing a crash. 
mean_dist = np.mean([df1['distance'], df3['distance'], df5['distance']], axis=0)
df1 = df1[mean_dist > 10]
df3 = df3[mean_dist > 10]
df5 = df5[mean_dist > 10]

# Filtre Gaussien
df1['Value'] = gaussian_filter1d(df1['Value'].values, 0.4)
df3['Value'] = gaussian_filter1d(df3['Value'].values, 0.4)
df5['Value'] = gaussian_filter1d(df5['Value'].values, 0.4)
# plt.figure()
# plt.plot(df1['distance'], df1['Value'], label='S1')

# Remove background contribution
df3['Value'] -= df3['Value'].rolling(window=7, center=True).min()
df5['Value'] -= df5['Value'].rolling(window=7, center=True).min()


# Remove Nan values from background removal
idx_nan = df3.loc[pd.isna(df3["Value"]), :].index.values
df1 = df1.drop(idx_nan).reset_index(drop=True)
df3 = df3.drop(idx_nan).reset_index(drop=True)
df5 = df5.drop(idx_nan).reset_index(drop=True)

S1_value, S1_dist = df1['Value'].values, df1['distance'].values
S3_value, S3_dist = df3['Value'].values, df3['distance'].values
S5_value, S5_dist = df5['Value'].values, df5['distance'].values

# plt.scatter(S1_dist, S1_value, label='S1')



# ------------ Find index peaks S1 (top) & S3, S5 (side) ------------

# For the sake of clarity, here is the notation used for the different vairables names:
# E  : Peaks (when a light fixture is detected)
# 1,3,5  : Sensor  number  (located on top of the lancube)
# S  : Simul (both top and side sendor detected a light)
# p  : prime (value just before or after the peaks)

print('Finding peaks and primes.')
idx_peak1,  _m  = find_peaks(S1_value, distance=2, prominence=0.005, height=0.005)
idx_peak3,  _m  = find_peaks(S3_value, distance=2, prominence=0.005, height=0.005)
idx_peak5,  _m  = find_peaks(S5_value, distance=2, prominence=0.005, height=0.005)


# Get peaks & traveled distance values
EV1, EV3, EV5 = S1_value[idx_peak1], S3_value[idx_peak3], S5_value[idx_peak5]
ED1, ED3 = df1['distance'].iloc[idx_peak1], df3['distance'].iloc[idx_peak3],
ED5 = df5['distance'].iloc[idx_peak5]

# plt.figure()
# plt.plot(S3_dist, S3_value)
# plt.plot(ED3, EV3, 'o')
# plt.show()


# Checking for side peaks close to top peak
idx_E1, idx_E3, idx_E5 = [], [], []
idx_ES13, idx_ES15 = [], [] # simul sensor 1
idx_ES31, idx_ES51 = [], [] # simul sensor 3 & 5

for pos in idx_peak1:
    
    d = df1['distance'].iloc[pos]  # traveled distance at peak (S1)
    
    mask_comb3 = ((d-10) < ED3) & (ED3 < (d+10)) # get simul peaks fom S1 and S3 (10m interval)
    mask_comb5 = ((d-10) < ED5) & (ED5 < (d+10)) # get simul peaks fom S1 and S5 (10m interval)
    comb3 = mask_comb3[mask_comb3]
    comb5 = mask_comb5[mask_comb5]

    if len(comb3) == 1:  # detection de un peak
        idx_ES13.append(pos) # add pos of idx sensor 1
        idx_ES31.append(comb3.index[0]) # add pos of idx sensor 3
    
    if len(comb5) == 1:
        idx_ES15.append(pos) # add pos of idx sensor 1
        idx_ES51.append(comb5.index[0]) # add pos of idx sensor 5

    if len(comb3) + len(comb5) == 0:  # only top peak
        idx_E1.append(pos)

# Get index side lights (peak only in S3 or S5)
idx_E3 = [i for i in idx_peak3 if i not in idx_ES31]
idx_E5 = [i for i in idx_peak5 if i not in idx_ES51]

# plt.figure()
# plt.plot(S1_dist, S1_value)
# plt.plot(S3_dist, S3_value)
# plt.plot(S1_dist[idx_E1], S1_value[idx_E1], 'o', label='S1')
# plt.plot(S1_dist[idx_ES13], S1_value[idx_ES13], 'o', label='S13')
# plt.plot(S1_dist[idx_ES15], S1_value[idx_ES15], 'o', label='S15')
# plt.plot(S3_dist[idx_ES31], S3_value[idx_ES31], 'o', label='S31')
# plt.legend()
# plt.show()



def find_prime(index_peaks, values, dist):
    """ Find prime value +- 2 points close to the index peak.
        Will take the back value if available, else the front one. """
        
    idx = np.array(index_peaks, dtype=int)
    idxp_front = []
    idxp_back  = []
    
    mask_front = np.zeros(len(idx), dtype=bool)
    mask_back  = np.zeros(len(idx), dtype=bool)
    
    for j, i in enumerate(idx):
        
        idxp = np.argwhere( (dist > dist[i]+2) & (dist < dist[i]+20) ).flatten()
        idxp = idxp[abs(values[idxp]) < abs(values[i]*0.90)] # minimal decrease of 10%
        idxp = idxp[abs(values[idxp]) > abs(values[i]*0.10)] # maximal decrease of 60%   
                
        if len(idxp > 0): # si on trouve un idx front
            idxp_front.append(idxp[0])
            mask_front[j] = True
            
        else:
            idxp = np.argwhere((dist > dist[i]-20) & (dist < dist[i]-2) ).flatten()  
            idxp = idxp[abs(values[idxp]) < abs(values[i]*0.90)] # minimal decrease of 10%     
            idxp = idxp[abs(values[idxp]) > abs(values[i]*0.10)] # maximal decrease of 60%          

            if len(idxp > 0): # si on trouve un idx back
                idxp_back.append(idxp[-1])
                mask_back[j] = True
    
    idx_prime = np.concatenate([idxp_back, idxp_front]).astype(int)
    idx_prime.sort()
                    
    
    # Take front value if availaible else take back
    out = np.zeros_like(idx)
    out[mask_front] =  1
    out[mask_back]  = -1
    mask = out != 0
    idx_peaks = idx[mask]
    out = out[mask]
    
    return idx_prime, idx_peaks, out, mask


# Calling find prime function to get index
idx_E1p,   idx_E1,   out1,  del1 = find_prime(idx_E1,   S1_value,  S1_dist)
idx_E3p,   idx_E3,   out3,  _del = find_prime(idx_E3,   S3_value,  S3_dist)
idx_E5p,   idx_E5,   out5,  _del = find_prime(idx_E5,   S5_value,  S5_dist)
idx_ES13p, idx_ES13, outS3, del3 = find_prime(idx_ES13, S1_value,  S1_dist)
idx_ES15p, idx_ES15, outS5, del5 = find_prime(idx_ES15, S1_value,  S1_dist)



# ----- Get peaks and prime values -----

# Take the top values when simul
EVS13, EDS13 = S1_value[idx_ES13], S1_dist[idx_ES13]
EVS15, EDS15 = S1_value[idx_ES15], S1_dist[idx_ES15]

EVS13p, EDS13p  = S1_value[idx_ES13p],  S1_dist[idx_ES13p]
EVS15p, EDS15p  = S1_value[idx_ES15p],  S1_dist[idx_ES15p]

# Get the values of S3 or S5 when simul
EVS31 = S3_value[idx_ES13]
EDS31 = S3_dist[idx_ES13] 
EVS51 = S5_value[idx_ES15]

EV1, ED1 = S1_value[idx_E1],  S1_dist[idx_E1]
EV3, ED3 = S3_value[idx_E3],  S3_dist[idx_E3]
EV5, ED5 = S5_value[idx_E5],  S5_dist[idx_E5]

EV1p, ED1p = S1_value[idx_E1p], S1_dist[idx_E1p]
EV3p, ED3p = S3_value[idx_E3p], S3_dist[idx_E3p]
EV5p, ED5p = S5_value[idx_E5p], S5_dist[idx_E5p]

# plt.figure()
# plt.plot(df1['distance'], df1['Value'], label='S1')
# plt.plot(df3['distance'], df3['Value'], label='S3')
# plt.plot(EDS31, EVS31, 'o', c='g')
# plt.plot(EDS13, EVS13, 'o', c='g')
# plt.plot(EDS15, EVS15, 'o', c='g')
# plt.plot(ED1, EV1, 'o', c='r')
# plt.plot(ED3, EV3, 'o', c='r')
# plt.plot(ED1p, EV1p, 'o', c='pink')
# plt.plot(ED3p, EV3p, 'o', c='pink')
# plt.legend()
# plt.show()


# ----- Determining side of detection -----
side_1 = np.full(len(EV1), np.nan)
side_3 = np.full(len(EV3), 'right')
side_5 = np.full(len(EV5), 'left')
side_S3 = np.full(len(EVS13), 'right')
side_S5 = np.full(len(EVS15), 'left')


# ------------ Getting lights characteristics ------------
print('Getting lights characteristics.')

idx_top_all = np.concatenate([idx_E1, idx_ES13, idx_ES15])  # Top peaks idx from only S1 and simul S1
MRGB_top_all = np.stack(( df1['Red'].iloc[idx_top_all].values,
                          df1['Green'].iloc[idx_top_all].values,
                          df1['Blue'].iloc[idx_top_all].values,
                          df1['IR'].iloc[idx_top_all]), axis=-1 )

# Concatening S3 & S5 dataframe while maintening index order
MRGB_3 = np.stack( (df3['Red'].iloc[idx_E3],
                    df3['Green'].iloc[idx_E3],
                    df3['Blue'].iloc[idx_E3],
                    df3['IR'].iloc[idx_E3]), axis=-1 )

MRGB_5 = np.stack( (df5['Red'].iloc[idx_E5],
                    df5['Green'].iloc[idx_E5],
                    df5['Blue'].iloc[idx_E5],
                    df5['IR'].iloc[idx_E5]), axis=-1 )

M_RGBI = np.concatenate((MRGB_top_all, MRGB_3, MRGB_5), axis=0) # Combine RGB arrays

MRBI_G = np.vstack([ (M_RGBI[:,0]/M_RGBI[:,1])*0.14, # R/G
                     (M_RGBI[:,2]/M_RGBI[:,1]), # B/G
                     (M_RGBI[:,3]/M_RGBI[:,1])]).T  # I/G



# -------  Reading lights datas -------
df_lights = pd.read_csv('spectrum_colors.csv')

lights_RBI_G = np.vstack([df_lights['r/g']*0.14, df_lights['b/g'], df_lights['i/g']])
dist_color = np.sum((MRBI_G[:,:,None] - lights_RBI_G)**2, 1)

idx_closest = np.argsort(dist_color)[:,:1]
closest_tech = df_lights['tech'].values[idx_closest]


# Distance between peaks and prime
D1  = abs(ED1 - ED1p)
D3  = abs(ED3 - ED3p)
D5  = abs(ED5 - ED5p)
DS3 = abs(S1_dist[idx_ES13] - S1_dist[idx_ES13p])
DS5 = abs(S1_dist[idx_ES15] - S1_dist[idx_ES15p])

        
# Horizontal distance between Lan3 and lights fixture
d1  = np.full(len(D1), 0)
d3  = (D3 * (EV3p/EV3)**(1/3)) / (np.sqrt(1 - (EV3p/EV3**(2/3)) ))  # (Eq. 27)
d5  = (D5 * (EV5p/EV5)**(1/3)) / (np.sqrt(1 - (EV5p/EV5**(2/3)) ))  # (Eq. 27)

dS3 = DS3 / np.sqrt( ( (EVS13/EVS13p)**(2/3) * \
                     ( ((EVS13/EVS31)**2) +1) ) \
                     - ((EVS13/EVS31)**2) -1  )   # (Eq. 14)

dS5 = DS5 / np.sqrt( ( (EVS15/EVS15p)**(2/3) * \
                     ( ((EVS15/EVS51)**2) +1) ) \
                     - ((EVS15/EVS51)**2) -1  )  # (Eq. 14)
 

# Light fixture height.
H1    = (D1 * ((EV1p/EV1)**(1/3)) / np.sqrt(1 - ((EV1p/EV1)**(2/3))) ) + h  # (Eq. 21)
H3    = np.full(len(D3), h)  # lights with same hights as Lan3
H5    = np.full(len(D5), h)  # lights with same hights as Lan3
HS3 = dS3 * (EVS13/EVS31) + h  # (Eq. 15)
HS5 = dS5 * (EVS15/EVS51) + h  # (Eq. 15)


# Line between light and lancube (Orthogonal) 
EO1  = df1['lux'].iloc[idx_E1].values
EO3  = df3['lux'].iloc[idx_E3].values
EO5  = df5['lux'].iloc[idx_E5].values
EOS3 = df1['lux'].iloc[idx_ES13].values * (np.sqrt((HS3 - h)**2 + HS3**2))\
        / (HS3 - h) # (Eq. 16)
EOS5 = df1['lux'].iloc[idx_ES15].values * (np.sqrt((HS5 - h)**2 + HS5**2))\
        / (HS5 - h) # (Eq. 16)

# Concatenate scenarios data
d = np.concatenate([d1, dS3, dS5, d3, d5])
D = np.concatenate([D1, DS3, DS5, D3, D5])
H = np.concatenate([H1, HS3, HS5, H3, H5])
side = np.concatenate([side_1, side_S3, side_S5, side_3, side_5])
EO   = np.concatenate([EO1, EOS3, EOS5, EO3, EO5])
out  = np.concatenate([out1, outS3, outS5, out3, out5])


# Accessing corrresponding ULOR
ULOR = np.zeros(len(closest_tech))
for i, techs in enumerate(closest_tech):
    ULOR[i] = df_lights.loc[df_lights['tech'] == techs[0], 'ULOR'].iloc[0]

flux = (2*np.pi*K*EO) * (d**2 + (H-h)**2) / (1 - ULOR)



# ------------- Calculate lamps coordinate -------------
print('Determining lamps coordinate.')

# Peaks coords
lat_peak = pd.concat([df1['lat'].iloc[idx_top_all], df3['lat'].iloc[idx_E3], df5['lat'].iloc[idx_E5]])
lon_peak = pd.concat([df1['lon'].iloc[idx_top_all], df3['lon'].iloc[idx_E3], df5['lon'].iloc[idx_E5]])
lat_peak = lat_peak.values
lon_peak = lon_peak.values


# Prime coords
idxp_top = np.concatenate((idx_E1p, idx_ES13p, idx_ES15p))
lat_prime = pd.concat([df1['lat'].iloc[idxp_top], df3['lat'].iloc[idx_E3p], df5['lat'].iloc[idx_E5p]])
lon_prime = pd.concat([df1['lon'].iloc[idxp_top], df3['lon'].iloc[idx_E3p], df5['lon'].iloc[idx_E5p]])
lat_prime = lat_prime.values
lon_prime = lon_prime.values

# Get unit vector
delta_lon = (lon_prime - lon_peak) * out
delta_lat = (lat_prime - lat_peak) * out

vec_x = delta_lon * np.cos(lat_peak*(np.pi/180)) /  \
        np.sqrt( (delta_lon*np.cos(lat_peak*(np.pi/180)))**2  + (delta_lat)**2 )  # (eq 33)

vec_y = delta_lat / np.sqrt( (delta_lon*np.cos(lat_peak*(np.pi/180)))**2  + (delta_lat)**2 ) # (eq 34)

epsilon = np.copy(side)
epsilon[epsilon == 'right'] = -np.pi/2
epsilon[epsilon == 'left']  = np.pi/2
epsilon[epsilon == 'nan'] = 0
epsilon = epsilon.astype(float)


# Convert unit vector pointing the light fixture
vec_xl = (-vec_y*np.sin(epsilon))  # (eq 35)
vec_yl = (vec_x*np.sin(epsilon))  # (eq 36)

# Light fixture position (meters)
xl = (d * vec_xl)  # (eq 37)
yl = (d * vec_yl)  # (eq 38)

lat_lights = ((180 * yl) / (np.pi*6373000)) + lat_peak # (eq 39)
lon_lights = ((180 * xl) / (np.pi*6373000*np.cos(lat_peak*(np.pi/180)))) + lon_peak # (eq 40)



# ----------------- Writing data -----------------
print('Writing data.')

lux = pd.concat([df1['lux'].iloc[idx_top_all], df3['lux'].iloc[idx_E3], df5['lux'].iloc[idx_E5]])
time = pd.concat([df1['Time'].iloc[idx_top_all], df3['Time'].iloc[idx_E3], df5['Time'].iloc[idx_E5]])

df_invent = pd.DataFrame({
            'lat_lights': lat_lights,
            'lon_lights': lon_lights,
            'H'     : list(H),
            'tech'  : list(closest_tech.flatten()),
            'lux'   : lux.tolist(),
            'flux'  : flux,
            'side'  : list(side),
            'R/G'   : list(MRBI_G[:,0]),
            'B/G'   : list(MRBI_G[:,1]),
            'd'     : list(d),
            'D'     : list(D),
            'lat_peaks' : lat_peak,
            'lon_peaks' : lon_peak,
            'E_perp': list(EO),
            'time'  : time.tolist(),
            'out' : out
            })

df_invent['h'] = h
# df_invent.to_csv(f'lan3_invent_inter_{filename}', index=False)


#& (df_invent['H'] > 4)

# 1- Weird values filter
df = df_invent[ ((df_invent['flux'] > 30000) | (df_invent['H'] > 22)) & (df_invent['H'] > 4) ]
# df.to_csv('weird_val_filter.csv')

update_H, df_coord = find_close_lights(df, df_invent, nb=10)
update_H = np.array(update_H)
update_H[np.isnan(update_H)] = 10
df_invent['H'].iloc[df.index.values] = update_H

df_update = df_invent


# Use mask only for none h height
mask_H = df_update['H'].values > h
H_p = df_update['H'].values[mask_H]
flux = flux[mask_H]
H = H[mask_H]
d = d[mask_H]
lat_peak = lat_peak[mask_H]
lon_peak = lon_peak[mask_H]
lat_lights = lat_lights[mask_H]
lon_lights = lon_lights[mask_H]


# ReDo calculations with update heights
flux_p = flux*( (H_p-h) / (H-h) )**2
d_p = d*(H_p-h) / (H-h)
lat_lights_p = lat_peak + (lat_lights-lat_peak) * (H_p-h)/(H-h)
lon_lights_p = lon_peak + (lon_lights-lon_peak) * (H_p-h)/(H-h)


# Update inventory
df_invent.loc[mask_H, 'lat_lights'] = lat_lights_p
df_invent.loc[mask_H, 'lon_lights'] = lon_lights_p
df_invent.loc[mask_H, 'd'] = d_p
df_invent.loc[mask_H, 'flux'] = flux_p
df_invent = df_invent.reset_index(drop=True)
# df_invent.to_csv('1_df_weird_val_filter.csv')



# Filter small flux
df_invent = df_invent[df_invent['flux'] > 250].reset_index(drop=True)
# df_invent.to_csv('2_df_small_flux_filter.csv')


# Filter multiple detections of the same light
df_invent = filter_multip_detections(df_invent, df_initial, prec_localisation)
# df_coord.to_csv('coord_multiple_detec.csv')
# df_invent.to_csv('3_df_multiple_detection.csv')

# Re-apply filter multip detection a second time
df_invent = filter_multip_detections(df_invent, df_initial, prec_localisation=12,
                                               condition_side=False)
# df_coord.to_csv('coord_multiple_detec.csv')
# df_invent.to_csv('3.1_df_multiple_detection.csv')



# Remove 2m HPS lights close to high lights
df_small = df_invent[df_invent['H'] == h].reset_index(drop=True)
df_small, df_coord = filter_small(df_small, df_invent, prec_localisation)
df_invent = pd.concat([df_small, df_invent[df_invent['H'] != h]]).reset_index(drop=True)
# df_coord.to_csv('coord_small_removed.csv')
# df_invent.to_csv('4_df_filter_small.csv')


# Final Inventory
df_invent.to_csv(f'lan3_invent_{filename}', index=False)

print('Done.')