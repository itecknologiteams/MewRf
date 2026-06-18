package com.hopeland.pda.example.hf;


import com.hopeland.pda.example.R;
import com.pda.rfid.EPCModel;
import com.pda.rfid.IAsynchronousMessage;
import com.pda.rfid.hf.HF;
import com.pda.rfid.hf.HFReader;
import com.util.BaseActivity;

import android.content.DialogInterface;
import android.content.res.Configuration;
import android.os.Bundle;
import android.os.Message;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Spinner;

public class ReadISO14443Activity extends BaseActivity implements
		IAsynchronousMessage {

	boolean busy = false;

	private Spinner sp_iso14443a_Model = null;
	private EditText tb_iso14443a_Uid = null;
	private Spinner sp_iso14443a_Block = null;
	private EditText tb_iso14443a_Data = null;
	private EditText tb_iso14443a_apdu = null;

	HF hfReader = HFReader.getHFInstance();

	static final int MSG_UPDATE_UID = MSG_USER_BEG + 1;

	@Override
	protected void msgProcess(Message msg) {
		switch (msg.what) {
		case MSG_UPDATE_UID:
			ShowUID(msg.obj.toString()); // 刷新列表
			break;
		default:
			super.msgProcess(msg);
			break;
		}
	}

	@Override
	protected void onCreate(Bundle savedInstanceState) {
		super.onCreate(savedInstanceState);
		this.setContentView(R.layout.hf_iso14443a);
		ChangeLayout(getResources().getConfiguration());

		try {
			getWindow().setFlags(
					WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON,
					WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
		} catch (Exception ex) {
			Log.d("Debug", "The initialization of abnormal:" + ex.getMessage());
		}

		showCustomBar(getString(R.string.btn_HFMenu_ISO14443A),
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

	private void ChangeLayout(Configuration newConfig) {
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

	@Override
	public void onConfigurationChanged(Configuration newConfig) {
		super.onConfigurationChanged(newConfig);
		ChangeLayout(newConfig);
	}

	// 扫描标签
	public void ReadISO4443A(View v) {
		//
		tb_iso14443a_Uid.setText("");
		String setParam = "IDEL";
		if (sp_iso14443a_Model != null) {
			setParam = sp_iso14443a_Model.getSelectedItem().toString();
		}
		if (setParam.equals("ALL")) {
			setParam = "52";
		} else {
			setParam = "26";
		}
		hfReader.GetISO14443ASN("0", setParam);
	}

	/*
	 * 读卡UID
	 */
	public void ShowUID(String uid) {
		tb_iso14443a_Uid.setText(uid);
	}

	// 卡挂起
	public void HaltISO14443A(View v) {
		String data = hfReader.HaltISO14443A();
		showMsg(data, null);
	}

	// 卡复位
	public void ResetISO14443A(View v) {
		String setParam = "0";
		String data = hfReader.ResetISO14443A(setParam);
		showMsg(data, null);
	}

	// RATS命令
	public void ReadIso14443aRATS(View v) {
		//
		tb_iso14443a_Data.setText("");
		String setParam = "0";
		if (sp_iso14443a_Block != null) {
			setParam = sp_iso14443a_Block.getSelectedItem().toString();
		}
		String data = hfReader.RATSiso14443a(setParam);
		//
		if (data.equals("")) {
			return;
		}
		if (data.contains("|")) {
			showMsg(data, null);
		} else {
			tb_iso14443a_Data.setText(data.substring(8, data.length()));
		}
	}

	// APDU命令
	public void APDU(View v) {
		//
		String param = "00 84 00 00 08";
		if (tb_iso14443a_apdu != null) {
			param = tb_iso14443a_apdu.getText().toString();
		}
		String data = hfReader.APDUiso14443a(param);
		if (data.equals("")) {
			return;
		}
		if (data.contains("|")) {
			showMsg(data, null);
		} else {
			showMsg(data.substring(8, data.length()), null);
		}
	}

	// Deselect命令
	public void Deselect(View v) {
		String data = hfReader.DeselctISO14443A();
		showMsg(data, null);
	}

	// 退出
	public void Back(View v) {
		ReadISO14443Activity.this.finish();
	}

	protected void Init() {
		if (!hfReader.OpenConnect(this)) { // 打开模块电源失败
			showMsg(getString(R.string.hf_low_power_info),
					new DialogInterface.OnClickListener() {
						@Override
						public void onClick(DialogInterface arg0, int arg1) {
							ReadISO14443Activity.this.finish();
						}
					});
		} else {
			sp_iso14443a_Model = (Spinner) this
					.findViewById(R.id.sp_iso14443a_Model);
			tb_iso14443a_Uid = (EditText) this
					.findViewById(R.id.tb_iso14443a_Uid);
			sp_iso14443a_Block = (Spinner) this
					.findViewById(R.id.sp_iso14443a_Block);
			tb_iso14443a_Data = (EditText) this
					.findViewById(R.id.tb_iso14443a_Data);
			tb_iso14443a_apdu = (EditText) this
					.findViewById(R.id.tb_iso14443a_apdu);
			tb_iso14443a_apdu.setText("00 84 00 00 08");
		}
	}

	protected void Dispose() {
		hfReader.CloseConnect();
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
		Dispose();
	}

	@Override
	protected void onResume() {
		// 待机恢复
		super.onResume();
		Init();
	}

	@Override
	public void OutPutEPC(EPCModel model) {
		try {
			sendMessage(MSG_UPDATE_UID, model._EPC);
		} catch (Exception ex) {
			Log.d("Debug", "Read the tag serial number exception:" + ex.getMessage());
		}
	}

}
