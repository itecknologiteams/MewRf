package com.hopeland.pda.example.uhf;

import java.util.HashMap;

import com.hopeland.pda.example.R;
import com.port.Adapt;
import com.pda.rfid.IAsynchronousMessage;
import com.pda.rfid.uhf.UHF;
import com.pda.rfid.uhf.UHFReader;
import com.util.BaseActivity;

import android.annotation.SuppressLint;
import android.content.DialogInterface;
import android.content.res.Configuration;
import android.util.Log;
import android.view.ViewGroup;
import android.widget.LinearLayout;

/**
 * @author RFID_C Base Activity
 */
public class UHFBaseActivity extends BaseActivity {

	static Boolean _UHFSTATE = false; // 模块是否已经打开
	// static int _PingPong_ReadTime = 10000; // 默认是100:3
	// static int _PingPong_StopTime = 300;
	static int _NowAntennaNo = 1; // 读写器天线编号
	static int _UpDataTime = 0; // 重复标签上传时间，控制标签上传速度不要太快
	static int _Max_Power = 30; // 读写器最大发射功率
	static int _Min_Power = 0; // 读写器最小发射功率

	static int low_power_soc = 10;

	public static UHF CLReader = UHFReader.getUHFInstance();

	/**
	 * UHF initialization
	 * @param log Interface callback method
	 * @return Whether the initialization was successful
	 */
	public Boolean UHF_Init(IAsynchronousMessage log) {
		Boolean rt = false;
		try {
			if (_UHFSTATE == false) {
				boolean ret = UHFReader.getUHFInstance().OpenConnect(log);
				if (ret) {
                    rt = true;
					_UHFSTATE = true;
				}

				Thread.sleep(500);
			} else {
				rt = true;
			}
		} catch (Exception ex) {
			Log.d("debug", "On the UHF electric abnormal:" + ex.getMessage());
		}
		return rt;
	}

	/**
	 * UHF closes connection
	 */
	public void UHF_Dispose() {
		if (_UHFSTATE == true) {
            UHFReader._Config.CloseConnect();
			_UHFSTATE = false;
		}
	}

	/**
	 * Acquire the read-write ability of the reader
	 */
	@SuppressLint("UseSparseArrays")
	@SuppressWarnings("serial")
	protected void UHF_GetReaderProperty() {
        String propertyStr = UHFReader._Config.GetReaderProperty();
		//Log.d("Debug", "Get Reader Property:" + propertyStr);
		String[] propertyArr = propertyStr.split("\\|");
		HashMap<Integer, Integer> hm_Power = new HashMap<Integer, Integer>() {
			{
				put(1, 1);
				put(2, 3);
				put(3, 7);
				put(4, 15);
			}
		};
		if (propertyArr.length > 3) {
			try {
				_Min_Power = Integer.parseInt(propertyArr[0]);
				_Max_Power = Integer.parseInt(propertyArr[1]);
				int powerIndex = Integer.parseInt(propertyArr[2]);
				_NowAntennaNo = hm_Power.get(powerIndex);
			} catch (Exception ex) {
				Log.d("Debug", "Get Reader Property failure and conversion failed!");
			}
		} else {
			Log.d("Debug", "Get Reader Property failure");
		}
	}

	/**
	 * Set tag upload parameters
	 */
	protected void UHF_SetTagUpdateParam() {
        String searchRT = UHFReader._Config.GetTagUpdateParam();
        String[] arrRT = searchRT.split("\\|");
		if (arrRT.length >= 2) {
			int nowUpDataTime = Integer.parseInt(arrRT[0]);
			Log.d("Debug", "Check the label to upload time:" + nowUpDataTime);
			if (_UpDataTime != nowUpDataTime) {
                UHFReader._Config.SetTagUpdateParam(_UpDataTime,0);//RSSIFilter
				Log.d("Debug", "Sets the label upload time...");
			} else {

			}
		} else {
			Log.d("Debug", "Query tags while uploading failure...");
		}
	}

    //Determine the backup power
    protected Boolean canUsingBackBattery() {
        if (Adapt.getPowermanagerInstance().getBackupPowerSOC() < low_power_soc) {
            return false;
        }
        return true;
    }

	/**
	 *
	 */
	protected boolean UHF_CheckReadResult(int retval) {
		if (99 == retval) {
			showMsg(getString(R.string.uhf_read_power_over),
					new DialogInterface.OnClickListener() {
						@Override
						public void onClick(DialogInterface dialog, int which) {
							UHFBaseActivity.this.finish();
						}
					});
			return false;
		}
		return true;
	}


    /**
     * Fit the screen
     */
    protected void ChangeLayout(Configuration newConfig) {
        LinearLayout main = (LinearLayout)findViewById(R.id.view_split_main);
        LinearLayout left = (LinearLayout)findViewById(R.id.view_split_left);
        LinearLayout right = (LinearLayout)findViewById(R.id.view_split_right);

        if (newConfig.orientation == Configuration.ORIENTATION_LANDSCAPE) { //当前屏幕为横屏
            main.setOrientation(LinearLayout.HORIZONTAL);

            LinearLayout.LayoutParams leftParam = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, (float) 0.5);
            LinearLayout.LayoutParams rightParam = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.MATCH_PARENT, (float) 0.5);

            leftParam.setMargins(0, 0, 10, 0);
            rightParam.setMargins(10, 0, 0, 0);

            left.setLayoutParams(leftParam);
            right.setLayoutParams(rightParam);

        } else { // 当前屏幕为竖屏
            main.setOrientation(LinearLayout.VERTICAL);

            LinearLayout.LayoutParams leftParam = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            LinearLayout.LayoutParams rightParam = (new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

            leftParam.setMargins(0, 0, 0, 0);
            rightParam.setMargins(0, 0, 0, 0);

            left.setLayoutParams(leftParam);
            right.setLayoutParams(rightParam);
        }

    }


}
