package com.hopeland.pda.example.dlt;

import com.hopeland.pda.example.R;
import com.util.BaseActivity;

import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.view.WindowManager;

public class MenuActivity extends BaseActivity {

	String TAG = "MR:Menu";

	public void onMeterRead(View v) {
		Log.i(TAG, "goto meter read");
//		// 调用读取电表参数界面
//		Intent meterReadIntent = new Intent();
//		meterReadIntent.setClass(MenuActivity.this, MeterReadActivity.class);
//		startActivity(meterReadIntent);
	}

	public void onMeterSetting(View v) {
		Log.i(TAG, "goto meter setting");
//		// 调用设置读取电表参数界面
//		Intent meterSettingIntent = new Intent();
//		meterSettingIntent.setClass(MenuActivity.this,
//				MeterSettingActivity.class);
//		startActivity(meterSettingIntent);
	}

	public void onFreeSend(View v) {
		Log.i(TAG, "goto free send and recv");
		// 嗲用硬件使用情况界面
		Intent FreeSendIntent = new Intent();
		FreeSendIntent.setClass(MenuActivity.this, FreeSendctivity.class);
		startActivity(FreeSendIntent);
	}

	public void onBack(View v) {
		finish();
	}

	@Override
	protected void onCreate(Bundle savedInstanceState) {
		super.onCreate(savedInstanceState);
		setContentView(R.layout.dlt_main);
		try {
			getWindow().setFlags(
					WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON,
					WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
		} catch (Exception ex) {
			Log.d("Debug", "The initialization of abnormal:" + ex.getMessage());
		}

		showCustomBar(getString(R.string.btn_MainMenu_DLT),
				getString(R.string.str_back), null,
				R.drawable.left, 0,
				new View.OnClickListener() {
					@Override
					public void onClick(View v) {
						onBack(v);
					}
				},
				null
		);
	}

}
