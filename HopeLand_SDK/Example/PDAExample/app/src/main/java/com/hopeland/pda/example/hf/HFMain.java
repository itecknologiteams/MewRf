package com.hopeland.pda.example.hf;

import android.content.Intent;
import android.os.Bundle;
import android.os.Message;
import android.util.Log;
import android.view.View;
import android.view.WindowManager;

import com.hopeland.pda.example.R;
import com.pda.rfid.EPCModel;
import com.pda.rfid.IAsynchronousMessage;
import com.pda.rfid.hf.HF;
import com.pda.rfid.hf.HFReader;
import com.util.BaseActivity;

public class HFMain extends BaseActivity implements IAsynchronousMessage {

	boolean busy = false;
	private final int MSG_SHOW_HF_VER = MSG_USER_BEG + 5;

	@Override
	protected void msgProcess(Message msg) {
		Intent intent;
		switch (msg.what) {
			case MSG_SHOW_HF_VER:
				if (msg.obj != null)
					showTip((String) msg.obj);
				break;
		}
		super.msgProcess(msg);
	}

	@Override
	protected void onCreate(Bundle savedInstanceState) {
		super.onCreate(savedInstanceState);
		this.setContentView(R.layout.hf_main);
		try {
			getWindow().setFlags(
					WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON,
					WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
		} catch (Exception ex) {
			Log.d("Debug", "The initialization of abnormal:" + ex.getMessage());
		}

		showCustomBar(getString(R.string.btn_MainMenu_HF),
				getString(R.string.str_back), null,
				R.drawable.left, 0,
				new View.OnClickListener() {
					@Override
					public void onClick(View v) {
						Back(v);
					}
				},
				null
		);
	}

	/**
	 * 打开ISO15693
	 */
	public void OpenISO15693Activity(View v) {
		Intent intent = new Intent();
		intent.setClass(HFMain.this, ReadISO15693Activity.class);
		startActivity(intent);
	}

	/**
	 * 打开ISO14443A
	 */
	public void OpenISO14443AActivity(View v) {
		Intent intent = new Intent();
		intent.setClass(HFMain.this, ReadISO14443Activity.class);
		startActivity(intent);
		// showMsg("Not open。", null);
	}

	/**
	 * 打开Mifare
	 */
	public void OpenMifareActivity(View v) {
		Intent intent = new Intent();
		intent.setClass(HFMain.this, ReadMifareActivity.class);
		startActivity(intent);
	}

	/**
	 * 获取android手机序列号
	 */
	public void OpenVersionActivity(View v) {
		if (isFastClick()) {
			return;
		}

		new Thread() {
			@Override
			public void run() {
				sendMessage(MSG_SHOW_WAIT,
						getString(R.string.str_please_waitting));
				String vStr = "- BaseBand: ";
				HF hfReader = HFReader.getHFInstance();
				if (hfReader.OpenConnect(HFMain.this)) { // 模块电源失败
					vStr += hfReader.GetReaderInformation();
				} else {
					vStr += "null";
				}
				hfReader.CloseConnect();

				sendMessage(MSG_SHOW_HF_VER, vStr);
				sendMessage(MSG_HIDE_WAIT, null);
			};
		}.start();

	}

	// 退出
	public void Back(View v) {
		HFMain.this.finish();
	}

	@Override
	protected void onDestroy() {
		// 释放
		super.onDestroy();
	}

	@Override
	protected void onPause() {
		// 待机锁屏
		super.onPause();
	}

	@Override
	protected void onResume() {
		// 待机恢复
		super.onResume();
	}

	@Override
	public void OutPutEPC(EPCModel model) {

	}

}
